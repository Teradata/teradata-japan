# -*- coding: utf-8 -*-

import os
import csv
import gzip
import sys
import json
from datetime import datetime
from glob import glob
from logging import getLogger
from getpass import getpass
import teradatasql
import toml
from tqdm import tqdm
logger = getLogger(__name__)


def _read_toml(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as f:
        x = toml.load(f)
    return x


class Session:
    def __init__(self, tdparams: dict):
        self.conn = teradatasql.connect(**tdparams)

    def __del__(self):
        try:
            id = self.id
            self.conn.close()
            logger.debug(f"Session {id} closed")
        except Exception as e:
            pass
            # If close method fails, then the connection is likely to have been closed already
            #logger.warning("Failed to close the database connection: %s", e)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        try:
            id = self.id
            self.conn.close()
            logger.debug(f"Session {id} closed")
        except Exception as e:
            pass
            # If close method fails, then the connection is likely to have been closed already
            #logger.warning("Failed to close the database connection: %s", e)

    @property
    def id(self):
        return self.get_query("SELECT SESSION")[0][0]

    @property
    def database(self):
        return self.get_query("SELECT DATABASE")[0][0]

    @property
    def user(self):
        return self.get_query("SELECT USER")[0][0]

    def get_query(self, query, params=None):
        logger.debug("Fetching with query:\n%s", query)
        c = self.conn.cursor()
        c.execute(query, params)
        x = c.fetchall()
        return x

    def exec_query(self, query, params=None, commit=False):
        logger.debug("Executing query:\n%s", query)
        c = self.conn.cursor()
        c.execute(query, params)
        if commit:
            c.execute("COMMIT")

    def validate_query(self, query, params=None):
        logger.debug("Validating query:\n%s", query)
        # check if the query is valid by calling its explanation
        c = self.conn.cursor()
        try:
            c.execute("EXPLAIN " + query, params)
            return True
        except Exception as e:
            logger.debug("Explain failed due to error of type %s:\n%s\nQuery (with params %s) is invalid:\n%s",
                         type(e), e, params, query)
            return False

    def database_exists(self, dbname):
        x = self.get_query("SELECT 1 FROM dbc.databasesV WHERE databasename = ?", (dbname,))
        return len(x) == 1

    def table_exists(self, dbname, tablename):
        x = self.get_query("SELECT 1 FROM dbc.tablesV WHERE databasename = ? AND tablename = ?", (dbname, tablename))
        return len(x) == 1

    def drop_table_if_exists(self, dbname, tablename):
        if self.table_exists(dbname, tablename):
            self.exec_query(f'DROP TABLE "{dbname}"."{tablename}"')

    def import_from_csv(self, csvfile, dbname, tablename, batchsize=10000, fastload=True):
        # We assume the table already exists
        logger.debug("Importing csvfile '%s' into '%s.%s'", csvfile, dbname, tablename)
        assert self.table_exists(dbname, tablename), "'{}.{}' must exist before importing".format(dbname, tablename)

        # We check the number of rows before, and make sure that all rows have been inserted at end
        nrows_before = self.get_query(f'SELECT COUNT(*) FROM "{dbname}"."{tablename}"')[0][0]
        logger.debug("Number of rows before import: %d", nrows_before)

        # We check the maximum line length to check the data size below
        _open = gzip.open if csvfile.endswith(".gz") else open
        with _open(csvfile, "rt", encoding="utf8") as f:
            max_row_len = max(len(line) for line in f)    
        logger.debug("maximum row length = %d", max_row_len)

        c = self.conn.cursor()
        # auto-commit: off
        self.conn.autocommit = False
        
        _open = gzip.open if csvfile.endswith(".gz") else open
        with _open(csvfile, "rt", encoding="utf8") as f:
            reader = csv.reader(f)
            header = next(reader)

            q = 'INSERT INTO "{}"."{}" VALUES ({})'.format(dbname, tablename, ",".join("?" for _ in header))
            if fastload:
                q = "{fn teradata_try_fastload} " + q
            q2 = "{fn teradata_nativesql}{fn teradata_get_warnings} " + q
            q3 = "{fn teradata_nativesql}{fn teradata_get_errors} " + q
            logger.debug("Insert query: '%s'", q)
            def _minibatch_insert(chunkdata):
                t1 = datetime.now()
                logger.debug("Start minibatch insertion to '%s.%s' (%d rows)", dbname, tablename, len(chunkdata))
                #c.executemany(q, chunkdata)
                c.execute(q, chunkdata)
                t2 = datetime.now()
                logger.debug("Finish minibatch insertion to '%s.%s' (%d rows, elapsed: %s)", dbname, tablename, len(chunkdata), t2-t1)
                # any warnings or errors?
                # ref: https://github.com/Teradata/python-driver/blob/master/samples/FastLoadBatch.py
                if fastload:
                    c.execute(q2)
                    logger.debug("Fastload warnings: %s", c.fetchall())
                    c.execute(q3)
                    logger.debug("Fastload errors: %s", c.fetchall())

            chunkdata = []
            rows_to_insert = 0  # We track the number rows to insert to check if all rows have been inserted successfully
            chunk_len = 0
            # We track the size of chunkdata so that we won't exceed the 1MB of a SQL request
            # https://support.teradata.com/community?id=community_question&sys_id=3e06c72f1b57fb00682ca8233a4bcbf2
            for row in reader:
                this_row_len = sum(len(v) for v in row) + len(q)
                close_size_limit = ( chunk_len + this_row_len > 0.9 * 10**6 / 4)  
                # Here, we assume the limit is 10**6 = 1MB, and allow for 10% buffer
                # Further, we assume that each letter consumes 4 bytes, which is conservative because a unicode letter is only 2 bytes
                if close_size_limit:
                    logger.debug("We are close to the size limit: current length: %d, this row length: %d", chunk_len, this_row_len)
                if len(chunkdata) >= batchsize or close_size_limit:
                    _minibatch_insert(chunkdata)
                    rows_to_insert += len(chunkdata)
                    chunkdata.clear()
                    chunk_len = 0

                # convert empty value to None
                chunkdata.append([None if v=="" else v for v in row])
                chunk_len += this_row_len
                #logger.debug("Current length: %d", chunk_len)
            if len(chunkdata) > 0:
                _minibatch_insert(chunkdata)
                rows_to_insert += len(chunkdata)

        logger.debug("Commiting the insert result")
        self.conn.commit()
        self.conn.autocommit = True

        # Check the number of rows after import
        nrows_after = self.get_query(f"SELECT COUNT(*) FROM {dbname}.{tablename}")[0][0]
        diff = nrows_after - nrows_before
        if diff == rows_to_insert:
            logger.debug("All rows have been inserted! %d --> %d (diff: %d)", nrows_before, nrows_after, diff)
        else:
            logger.error("It seeems we could not import all rows: %d --> %d (diff: %d) but we have %d rows to insert",
                        nrows_before, nrows_after, diff, rows_to_insert)
            raise RuntimeError("It seeems we could not import all rows: {} --> {} (diff: {}) but we have {} rows to insert".format(
                nrows_before, nrows_after, diff, rows_to_insert))


class Database:
    def __init__(self, dbdir, session):
        self.dbname = os.path.basename(dbdir)
        self.tomlfile = os.path.join(dbdir, "ddl.toml")
        self.ddl = _read_toml(self.tomlfile)
        self.session = session

    @property
    def perm_size(self):
        return self.ddl["perm_size"]

    def create_or_modify(self, if_exists="modify", parent_db=None, users=None):
        # In case the target database already exists,
        #   if_exists == modify    --> Modify the db properties
        #   if_exists == replace   --> Delete the database and recreate
        #                              but will fail if the database has an object
        #   otherewise             --> Do nothing
        
        if self.session.database_exists(self.dbname) and if_exists == "replace":
            logger.debug("Deleting the existing database '%s'", self.dbname)
            q = f'DROP DATABASE "{self.dbname}"'
            self.session.exec_query(q)

        if not self.session.database_exists(self.dbname):
            logger.debug("Creating the database '%s'", self.dbname)
            parent_db = parent_db or self.session.database
            q = f"""
            CREATE DATABASE "{self.dbname}" FROM "{parent_db}" AS
            PERMANENT = {self.perm_size}
            """
            self.session.exec_query(q)
        elif if_exists == "modify":
            logger.debug("Modifying the database '%s'", self.dbname)
            q = f"""
            MODIFY DATABASE "{self.dbname}" AS
            PERMANENT = {self.perm_size}
            """
            self.session.exec_query(q)
        else:
            logger.debug("We neither create nor modify the database '%s'", self.dbname)
        if users is not None:
           for user in users:
                logger.debug("Granting select access to the {user}")
                self.session.exec_query(f'GRANT SELECT ON {self.dbname} TO "{user}"')
        logger.debug("Done with create or modify '%s'", self.dbname)


class Table:
    def __init__(self, tabledir, session, session_insert):
        self.dbname = os.path.basename(os.path.dirname(tabledir))
        self.table = os.path.basename(tabledir)
        self.tomlfile = os.path.join(tabledir, "ddl.toml")
        # csv file is either data.csv.gz or data.csv
        tmp = os.path.join(tabledir, "data.csv.gz")
        if os.path.isfile(tmp):
            self.csvfile = tmp
        else:
            self.csvfile = os.path.join(tabledir, "data.csv")
        self.ddl = _read_toml(self.tomlfile)
        self.session = session
        self.session_insert = session_insert

    @property
    def has_udf(self):
        geo = self.ddl.get("geometry_columns", [])
        if len(geo) > 0:
            return True
        # in the future, we may support JSON or alike
        return False

    @property
    def _create_ddl(self):
        tabletype = "MULTISET" if self.ddl["multiset"] else "SET"
        columns = ", ".join(f'"{name}" {type_}' for name, type_ in zip(self.ddl["column_names"], self.ddl["column_types"]))
        pis = self.ddl.get("primary_index", [])
        pis = "NO PRIMARY INDEX" if len(pis) == 0 else "PRIMARY INDEX ({})".format(",".join(pis))
        # sis = self.ddl.get("secondary_index", [])
        # sis = "" if len(sis) == 0 else ",".join(
        #     "{unique} INDEX ( {cols} ) {orders} ".format(
        #         unique="UNIQUE" if si.get("unique") else "",
        #         cols=",".join(si["columns"]), 
        #         orders="" if len(si["order_by"]) == 0 else "ORDER BY ({})".format(",".join(si["order_by"]))
        #     ) for si in sis)
        # We will create SIs after we insert rows to avoid error
        # "3621   Cannot load table %TVMID unless secondary indexes and join indexes are removed"
        partitions = self.ddl.get("partition_by", [])
        partitions = (
            "" if len(partitions) == 0 else  # no partitions
            f"PARTITION BY {partitions[0]}" if len(partitions) == 1 else  # single partition
            "PARTITION BY ( {} )".format(",".join(partitions))  # multi-level partitions
        )
        fallback = "" if self.ddl["fallback"] else "NO"
        beforejournal = "" if self.ddl["before_journal"] else "NO"
        afterjournal = "" if self.ddl["after_journal"] else "NO"
        q = f"""
        CREATE {tabletype} TABLE {self.dbname}.{self.table}
        ,{fallback} FALLBACK
        ,{beforejournal} BEFORE JOURNAL
        ,{afterjournal} AFTER JOURNAL
        ( {columns} )
        {pis}
        {partitions}
        """
        return q
    
    @property
    def _add_index_queries(self):
        sis = self.ddl.get("secondary_index", [])
        sis = [
            "CREATE {unique} INDEX ( {cols} ) {orders} ON {db}.{table}".format(
                unique="UNIQUE" if si.get("unique") else "",
                cols=",".join(si["columns"]), 
                orders="" if len(si["order_by"]) == 0 else "ORDER BY ({})".format(",".join(si["order_by"])),
                db=self.dbname,
                table=self.table
            ) for si in sis
        ]
        return sis

    def create(self, if_exists="replace", no_insert=False):
        # In case the target database already exists,
        #   if_exists == replace   --> Delete the table and recreate
        #   otherewise             --> Do nothing
        if self.session.table_exists(self.dbname, self.table):
            if if_exists == "replace":
                logger.debug("Deleting the existing table '%s.%s'", self.dbname, self.table)
                q = f"DROP TABLE {self.dbname}.{self.table}"
                self.session.exec_query(q)
            else:
                logger.debug("We do not create the table '%s.%s' since it already exists", self.dbname, self.table)
                return
        
        if self.has_udf:
            logger.debug("Switching to the procedure for tables with geometry column")
            return self._create_with_udf(no_insert=no_insert)
        
        logger.debug("Creating table '%s.%s'", self.dbname, self.table)
        q = self._create_ddl
        self.session.exec_query(q)

        if no_insert:
            logger.debug("Skip inserting rows to '%s.%s'", self.dbname, self.table)
        else:
            logger.debug("Populating rows from '%s' into '%s.%s", self.csvfile, self.dbname, self.table)
            fastload = not self.ddl.get("no_fastload", False)
            self.session_insert.import_from_csv(self.csvfile, self.dbname, self.table, fastload=fastload)
        
        qs = self._add_index_queries
        if len(qs) > 0:
            logger.debug("Create index queryes:\n%s", "\n".join(qs))
        for i, q in enumerate(qs):
            logger.debug("Adding index %d / %d", i+1, len(qs))
            self.session.exec_query(q)
        
        logger.debug("Done with create '%s.%s'", self.dbname, self.table)

    @property
    def _intermediate_table(self):
        return f'{self.table}_temp'

    def _is_geometry(self, colname):
        return colname in self.ddl["geometry_columns"]

    def _is_udf(self, colname):
        # We may want to more udf columns in the future
        return self._is_geometry(colname)

    @property
    def _create_intermediate_ddl_with_udf(self):
        tabletype = "MULTISET" if self.ddl["multiset"] else "SET"
        # check the character length of each columns
        logger.debug("Checking the character lengths of columns")
        _open = gzip.open if self.csvfile.endswith(".gz") else open
        with _open(self.csvfile, "rt", encoding="utf8") as f:
            reader = csv.reader(f)
            header = next(reader)
            char_lengths = [0] * len(header)
            for row in reader:
                for j, v in enumerate(row):
                    if len(v) > char_lengths[j]:
                        char_lengths[j] = len(v)
        logger.debug("Character lengths: %s", dict(zip(self.ddl["column_names"], char_lengths)))
        coltypes = []
        for colname, typename, length in zip(self.ddl["column_names"], self.ddl["column_types"], char_lengths):
            if self._is_udf(colname):
                if length <= 64000:
                    t = f"VARCHAR({length}) CHARACTER SET LATIN"
                elif length <= 2097088000:
                    t = f"CLOB({length}) CHARACTER SET LATIN"
                coltypes.append(t)
            else:
                coltypes.append(typename)
        columns = ", ".join(f'"{name}" {type_}' for name, type_ in zip(self.ddl["column_names"], coltypes))
        
        q = f"""
        CREATE {tabletype} TABLE {self.dbname}.{self._intermediate_table}
        ,NO FALLBACK, NO BEFORE JOURNAL, NO AFTER JOURNAL
        ( {columns} )
        NO PRIMARY INDEX
        """
        return q

    @property
    def _ctas_query_with_udf(self, no_insert=False):
        tabletype = "MULTISET" if self.ddl["multiset"] else "SET"
        pis = self.ddl.get("primary_index", [])
        pis = "NO PRIMARY INDEX" if len(pis) == 0 else "PRIMARY INDEX ({})".format(",".join(pis))
        partitions = self.ddl.get("partition_by", [])
        partitions = (
            "" if len(partitions) == 0 else  # no partitions
            f"PARTITION BY {partitions[0]}" if len(partitions) == 1 else  # single partition
            "PARTITION BY ( {} )".format(",".join(partitions))  # multi-level partitions
        )
        fallback = "" if self.ddl["fallback"] else "NO"
        beforejournal = "" if self.ddl["before_journal"] else "NO"
        afterjournal = "" if self.ddl["after_journal"] else "NO"
        withdata = "NO" if no_insert else ""

        epsg = [e for e in self.ddl["geometry_epsg"] if e is not None]
        if len(epsg) > 0:
            # we obtain the SRID in this system
            q = """
            SELECT AUTH_SRID, SRID FROM SYSSPATIAL.SPATIAL_REF_SYS 
            WHERE AUTH_NAME = 'EPSG' AND AUTH_SRID IN ({})     
            """.format("?" * len(epsg))
            res = self.session.get_query(q, epsg)
            epsg_to_srid = dict(res)
            logger.debug("EPSG to SRID map: %s", epsg_to_srid)
        col_to_srid = {}
        for col, e in zip(self.ddl["geometry_columns"], self.ddl["geometry_epsg"]):
            col_to_srid[col] = None if e is None else epsg_to_srid.get(e)
        logger.debug("Column to SRID map: %s", col_to_srid)

        columns = []
        for c, t in zip(self.ddl["column_names"], self.ddl["column_types"]):
            # support other UDF as we need, e.g. JSON
            if self._is_geometry(c):
                # add srid if available
                srid = col_to_srid[c]
                col_srid = c if srid is None else f"{c}, {srid}"
                # check the datasize of the column
                res = self.session.get_query(f"""
                    SELECT MAX(DataSize(NEW ST_Geometry({col_srid}))) FROM {self.dbname}.{self._intermediate_table}
                """)
                size = res[0][0]
                if size is None or size < 100:
                    size = 100
                columns.append(f"CAST(NEW ST_Geometry({col_srid}) AS ST_Geometry({size})) AS {c}")
            else:
                columns.append(c)
        columns = ",".join(columns)
        select_query = f"""
        SELECT
          {columns}
        FROM
          {self.dbname}.{self._intermediate_table}
        """

        q = f"""
        CREATE {tabletype} TABLE {self.dbname}.{self.table}
        ,{fallback} FALLBACK
        ,{beforejournal} BEFORE JOURNAL
        ,{afterjournal} AFTER JOURNAL
        AS ( {select_query} ) WITH {withdata} DATA
        {pis}
        {partitions}
        """
        return q

    def _create_with_udf(self, no_insert=False):
        # Before starting, the field limit size to a large value to avoid error "_csv.Error: field larger than field limit (131072)"
        # We set the limit as the maximum CLOB size because field larger than this won't be able to use anyways
        csv.field_size_limit(2097088000)  

        # This function creates a table with UDF columns (e.g. geometry)
        # first, we create intermediate table where UDF is replaced with character or CLOB
        # before creating the table, we delete the table if already exists
        temptable = self._intermediate_table
        logger.debug("Dropping the intermediate table '%s.%s', if exists", self.dbname, temptable)
        self.session.drop_table_if_exists(self.dbname, temptable)
        # create intermediate table
        logger.debug("Creating the intermediate table '%s.%s'", self.dbname, temptable)
        q = self._create_intermediate_ddl_with_udf
        self.session.exec_query(q)
        has_clob = (q.lower().find("clob") >= 0)  # if CLOB is in the table, we do not use fastload
        if has_clob:
            logger.debug("Intermediate DDL contains clob, so we won't try fastload")
        # insert data into the intermediate table
        logger.debug("Inserting rows into the intermediate table '%s.%s'", self.dbname, temptable)
        fastload = (not has_clob) and (not self.ddl.get("no_fastload", False))
        self.session_insert.import_from_csv(self.csvfile, self.dbname, temptable, fastload=fastload)
        # run CTAS query to create the target table
        logger.debug("Creating the target table '%s.%s' using the intermediate table '%s.%s'", self.dbname, self.table, self.dbname, temptable)
        q = self._ctas_query_with_udf
        self.session.exec_query(q)
        # finally, clean up the intermediate table
        logger.debug("Dropping the intermediate table '%s.%s'", self.dbname, temptable)
        self.session.drop_table_if_exists(self.dbname, temptable)

        # We reset the csv max field size, just in case this has any bad impact on other processes
        csv.field_size_limit(131072)
        logger.debug("Done with create '%s.%s' with geometry columns", self.dbname, self.table)


def setup_tdquiz(datadir="./data", verbose=True,
                 db_if_exists="skip", parent_db=None, table_if_exists="skip", no_insert=False, 
                 host="host.docker.internal", user="demo_user", password=None,
                 database="demo_user", encryptdata="true", dbs_port=1025, **params):
    params.update(dict(
        host=host, user=user, password=password or getpass("Password: "),
        database=database, encryptdata=encryptdata, dbs_port=dbs_port
    ))

    # create database
    databases = [d for d in glob(os.path.join(datadir, "*")) if os.path.isdir(d)]
    logger.debug("%d databases found: '%s'", len(databases), databases)
    for dbdir in tqdm(databases, desc="Create database") if verbose else databases:
        with Session(params) as session:
            database = Database(dbdir, session)
            database.create_or_modify(if_exists=db_if_exists, parent_db=parent_db)
        del session
    
    # create and populate tables
    tables = [d for d in glob(os.path.join(datadir, "*", "*")) if os.path.isdir(d)]
    logger.debug("%d tables found: '%s'", len(tables), tables)
    for tabledir in tqdm(tables, desc="Create table   ") if verbose else tables:
        # if tabledir.find("Tera") < 0:
        #     print("SKIP!")
        #     continue
        #session = Session(params)
        with Session(params) as session, Session(params) as session_insert:
            table = Table(tabledir, session, session_insert)
            table.create(if_exists=table_if_exists, no_insert=no_insert)
            del session, session_insert
    if verbose:
        print("We are ready!", file=sys.stderr)
