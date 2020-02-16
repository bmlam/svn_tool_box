CREATE OR REPLACE procedure "EDWH_TNSPARSER"."PKG_PARSE_TNS"
AS
/* test a block
comment */ 
procedure delete_uploaded_from_src (
	p_source_name varchar2, p_clob clob 
	-- before bracket
)
as
	lv number; 
begin
	for i in 1 .. 3 loop
		if true the null; end if;
	end loop;
/*
	case when true then null; 
	else-- test a line comment
		null;-- another line comment 
	end case; 
*/
end delete_uploaded_from_src;

BEGIN 	
	null;
END;
