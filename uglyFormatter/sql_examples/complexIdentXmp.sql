CREATE procedure "EDWH_TNSPARSER"."PKG_PARSE_TNS"
AS
--	l_row_count integer;
begin
	select 1 into l_row_count
	from schemaA.table_b@db_link.com ;
	select 2 into l_row_count
	from schemaA.table_b@db_link.com alias_2;
end ;

