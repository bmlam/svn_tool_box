CREATE OR REPLACE FUNCTION split_to_array ( pi_str VARCHAR2 )
RETURN ora_mining_varchar2_nt
AS
-- test examle:
-- begin
--     for rec in ( select column_value cv from  table ( split_to_array ( 'a,12,355ghf' ) )
--     )
--     loop
--         dbms_output.put_line ( rec.cv );
--     end loop;
-- end;

	l_return  ora_mining_varchar2_nt := ora_mining_varchar2_nt();
BEGIN
	select regexp_substr( pi_str ,'[^,]+', 1, level) 
	BULK COLLECT INTO l_return
	from dual
    connect by regexp_substr( pi_str , '[^,]+', 1, level) is not null
	;
	return l_return;
END;
/

show errors

