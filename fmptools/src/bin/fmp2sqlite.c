/* FMP Tools - A library for reading FileMaker Pro databases
 * Copyright (c) 2020 Evan Miller (except where otherwise noted)
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <libgen.h>

#include <sqlite3.h>

#include "../fmp.h"
#include "usage.h"

#define safe_append(p, base, max_len, ...) do { \
    size_t limit = (max_len) - ((p) - (base)); \
    int n = snprintf((p), limit, __VA_ARGS__); \
    if (n > 0) { \
        if ((size_t)n >= limit) { \
            (p) += limit - 1; \
        } else { \
            (p) += n; \
        } \
    } \
} while(0)

typedef struct fmp_sqlite_ctx_s {
    sqlite3 *db;
    sqlite3_stmt *insert_stmt;
    char *table_name;
    int last_row;
    fmp_column_array_t *columns;
} fmp_sqlite_ctx_t;

fmp_handler_status_t handle_value(int row, fmp_column_t *column, const char *value, void *ctxp) {
    fmp_sqlite_ctx_t *ctx = (fmp_sqlite_ctx_t *)ctxp;
    if (ctx->last_row != row && ctx->last_row > 0) {
        int rc = sqlite3_step(ctx->insert_stmt);
        if (rc != SQLITE_DONE) {
            fprintf(stderr, "Error inserting data into SQLite table: %s\n", sqlite3_errmsg(ctx->db));
            return FMP_HANDLER_ABORT;
        }
        rc = sqlite3_reset(ctx->insert_stmt);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "Error resetting INSERT statement: %s\n", sqlite3_errmsg(ctx->db));
            return FMP_HANDLER_ABORT;
        }
        sqlite3_clear_bindings(ctx->insert_stmt);
    }
    int param_idx = -1;
    if (value && value[0]) {
        printf("DEBUG VALUE: table='%s' row=%d col='%s' val='%s'\n", ctx->table_name, row, column->utf8_name, value);
    }
    for (int j = 0; j < ctx->columns->count; j++) {
        if (ctx->columns->columns[j].index == column->index) {
            param_idx = j + 1;
            break;
        }
    }
    if (param_idx == -1) {
        return FMP_HANDLER_OK;
    }
    int rc = sqlite3_bind_text(ctx->insert_stmt, param_idx, value, strlen(value), SQLITE_TRANSIENT);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error binding parameter: %s\n", sqlite3_errmsg(ctx->db));
        return FMP_HANDLER_ABORT;
    }
    ctx->last_row = row;
    return FMP_HANDLER_OK;
}

static size_t create_query_length(fmp_table_t *table, fmp_column_array_t *columns) {
    size_t len = 0;
    len += sizeof("CREATE TABLE \"\" ();");
    len += strlen(table->utf8_name);
    for (int j=0; j<columns->count; j++) {
        len += sizeof("\"\" TEXT")-1;
        len += strlen(columns->columns[j].utf8_name);
        if (j < columns->count) {
            len += sizeof(", ")-1;
        }
    }
    return len;
}

static size_t insert_query_length(fmp_table_t *table, fmp_column_array_t *columns) {
    size_t len = 0;
    len += sizeof("INSERT INTO \"\" () VALUES ();");
    len += strlen(table->utf8_name);
    for (int j=0; j<columns->count; j++) {
        len += sizeof("\"\"")-1;
        len += strlen(columns->columns[j].utf8_name);
        len += sizeof("\"\"")-1;
        len += sizeof("?NNNNN")-1;
        if (j < columns->count) {
            len += sizeof(", ")-1;
            len += sizeof(", ")-1;
        }
    }
    return len;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        print_usage_and_exit(argc, argv);
    }

    sqlite3 *db = NULL;
    char *zErrMsg = NULL;
    fmp_error_t error = FMP_OK;
    fmp_file_t *file = fmp_open_file(argv[1], &error);
    if (!file) {
        fprintf(stderr, "Error code: %d\n", error);
        return 1;
    }

    fmp_table_array_t *tables = fmp_list_tables(file, &error);
    if (!tables) {
        fprintf(stderr, "Error code: %d\n", error);
        return 1;
    }

    int rc = sqlite3_open_v2(argv[2], &db,
            SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error opening SQLite file\n");
        return 1;
    }

    rc = sqlite3_exec(db, "PRAGMA journal_mode = OFF;\n", NULL, NULL, &zErrMsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error setting journal_mode = OFF\n");
        return 1;
    }

    rc = sqlite3_exec(db, "PRAGMA synchronous = 0;\n", NULL, NULL, &zErrMsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error setting synchronous = 0\n");
        return 1;
    }

    char *create_query = NULL;
    char *insert_query = NULL;

    for (int i=0; i<tables->count; i++) {
        fmp_table_t *table = &tables->tables[i];
        fmp_column_array_t *columns = fmp_list_columns(file, table, &error);
        if (!columns) {
            fprintf(stderr, "Error code: %d\n", error);
            return 1;
        }
        if (columns->count == 0) {
            fprintf(stderr, "Warning: Table \"%s\" has 0 columns, skipping...\n", table->utf8_name);
            fmp_free_columns(columns);
            continue;
        }
        size_t create_query_len = create_query_length(table, columns) + columns->count * 32 + 65536;
        size_t insert_query_len = insert_query_length(table, columns) + columns->count * 32 + 65536;
        create_query = realloc(create_query, create_query_len);
        insert_query = realloc(insert_query, insert_query_len);

        char *p = create_query;
        char *q = insert_query;
        safe_append(p, create_query, create_query_len, "CREATE TABLE \"%s\" (", table->utf8_name);
        safe_append(q, insert_query, insert_query_len, "INSERT INTO \"%s\" (", table->utf8_name);
        for (int j=0; j<columns->count; j++) {
            fmp_column_t *column = &columns->columns[j];
            char *colname = strdup(column->utf8_name);
            size_t colname_len = strlen(colname);
            for (int k=0; k<colname_len; k++) {
                unsigned char c = (unsigned char)colname[k];
                if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c >= 128)) {
                    colname[k] = '_';
                }
            }
            // Check for duplicates in previous columns
            int duplicate_count = 1;
            for (int prev_idx = 0; prev_idx < j; prev_idx++) {
                fmp_column_t *prev_column = &columns->columns[prev_idx];
                char *prev_colname = strdup(prev_column->utf8_name);
                size_t prev_len = strlen(prev_colname);
                for (int k=0; k<prev_len; k++) {
                    unsigned char c = (unsigned char)prev_colname[k];
                    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c >= 128)) {
                        prev_colname[k] = '_';
                    }
                }
                if (strcasecmp(colname, prev_colname) == 0) {
                    duplicate_count++;
                }
                free(prev_colname);
            }
            if (duplicate_count > 1) {
                char *new_colname = malloc(colname_len + 16);
                sprintf(new_colname, "%s_%d", colname, duplicate_count);
                free(colname);
                colname = new_colname;
            }
            safe_append(p, create_query, create_query_len, "\"%s\" TEXT", colname);
            safe_append(q, insert_query, insert_query_len, "\"%s\"", colname);
            if (j < columns->count - 1) {
                safe_append(p, create_query, create_query_len, ", ");
                safe_append(q, insert_query, insert_query_len, ", ");
            }
            free(colname);
        }
        safe_append(p, create_query, create_query_len, ");");
        safe_append(q, insert_query, insert_query_len, ") VALUES (");
        for (int j=0; j<columns->count; j++) {
            safe_append(q, insert_query, insert_query_len, "?%d", j + 1);
            if (j < columns->count - 1)
                safe_append(q, insert_query, insert_query_len, ", ");
        }
        safe_append(q, insert_query, insert_query_len, ");");

        fprintf(stderr, "CREATE TABLE \"%s\"\n", table->utf8_name);
        rc = sqlite3_exec(db, create_query, NULL, NULL, &zErrMsg);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "Error creating SQL table: %s\n", zErrMsg);
            fprintf(stderr, "Statement was: %s\n", create_query);
            return 1;
        }

        sqlite3_stmt *stmt = NULL;
        rc = sqlite3_prepare_v2(db, insert_query, -1, &stmt, NULL);
        if (rc != SQLITE_OK) {
            fprintf(stderr, "Error preparing SQL statement: %d\n", rc);
            fprintf(stderr, "Statement was: %s\n", insert_query);
            return 1;
        }

        fmp_sqlite_ctx_t ctx = { .db = db, .table_name = table->utf8_name, .insert_stmt = stmt, .columns = columns };
        fmp_read_values(file, table, &handle_value, &ctx);
        if (ctx.last_row) {
            int rc = sqlite3_step(stmt);
            if (rc != SQLITE_DONE) {
                fprintf(stderr, "Error inserting data into SQLite table: %s\n", sqlite3_errmsg(db));
                return 1;
            }
        }
        sqlite3_finalize(stmt);
        fmp_free_columns(columns);
    }

    free(create_query);
    free(insert_query);
    fmp_free_tables(tables);
    sqlite3_close(db);
    fmp_close_file(file);

    return 0;
}
