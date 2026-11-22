"""S7: the MCP server's database user. query_zone_stats must not run as labadmin: create a user that can
read the marts schema and nothing else (decision: database role scope), with the RedshiftData resource.
The MCP server connects as it through the Data API's --db-user path (MCP_DB_USER, default lab_ro), so it
needs no password. Remember the mart is refreshed: grants must survive that.
"""

import dagster as dg

from ..resources import RedshiftData

MCP_DB_USER = "lab_ro"


@dg.asset(deps=["zone_hour_stats"], group_name="marts", kinds={"redshift"}, pool="redshift")
def mcp_reader(context: dg.AssetExecutionContext, redshift: RedshiftData) -> dg.MaterializeResult:
    """Ensure the read-only database user exists with SELECT privileges on marts only."""
    user_count = int(redshift.scalar(f"SELECT count(*) FROM pg_user WHERE usename = '{MCP_DB_USER}'") or 0)
    if user_count == 0:
        redshift.execute(f"CREATE USER {MCP_DB_USER} PASSWORD DISABLE;")

    # Apply least privilege grants and default privileges for future mart tables
    redshift.execute(
        f"REVOKE ALL ON SCHEMA ingest FROM {MCP_DB_USER};",
        f"REVOKE ALL ON SCHEMA staging FROM {MCP_DB_USER};",
        f"REVOKE CREATE ON SCHEMA marts FROM {MCP_DB_USER};",
        f"GRANT USAGE ON SCHEMA marts TO {MCP_DB_USER};",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA marts TO {MCP_DB_USER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO {MCP_DB_USER};",
    )

    # Verify privileges match the security baseline
    row = redshift.query(
        f"SELECT has_table_privilege('{MCP_DB_USER}', 'marts.zone_hour_stats', 'select') as read_marts, "
        f"has_table_privilege('{MCP_DB_USER}', 'marts.zone_hour_stats', 'insert') as write_marts, "
        f"has_schema_privilege('{MCP_DB_USER}', 'ingest', 'usage') as use_ingest, "
        f"has_schema_privilege('{MCP_DB_USER}', 'marts', 'create') as create_in_marts"
    )[0]
    read_marts = row.get("read_marts") in (True, "true", "t", 1, "1")
    write_marts = row.get("write_marts") in (True, "true", "t", 1, "1")
    use_ingest = row.get("use_ingest") in (True, "true", "t", 1, "1")
    create_in_marts = row.get("create_in_marts") in (True, "true", "t", 1, "1")

    context.log.info(
        f"mcp_reader privileges: read_marts={read_marts}, write_marts={write_marts}, "
        f"use_ingest={use_ingest}, create_in_marts={create_in_marts}"
    )
    if not (read_marts and not write_marts and not use_ingest and not create_in_marts):
        raise ValueError(f"mcp_reader privileges violation: {row}")

    return dg.MaterializeResult(
        metadata={
            "db_user": MCP_DB_USER,
            "read_marts": dg.MetadataValue.bool(read_marts),
            "write_marts": dg.MetadataValue.bool(write_marts),
            "use_ingest": dg.MetadataValue.bool(use_ingest),
            "create_in_marts": dg.MetadataValue.bool(create_in_marts),
        }
    )


mcp_reader_job = dg.define_asset_job(
    "mcp_reader_job",
    selection=dg.AssetSelection.assets(mcp_reader),
    description="Provision and verify the read-only database user for the MCP server.",
)
