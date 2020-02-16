
CREATE OR REPLACE EDITIONABLE 
procedure delete_uploaded_from_src (
	p_source_name varchar2, p_clob clob 
)
/***********************************************************************************/
as
	l_row_count integer;
begin
	pkg_utl_log.log('Deleting entry from source: '
		||p_source_name||' user: '''||nvl( v('APP_USER'), user) );
	--
	delete from tns_entry_uploaded
	where file_source = p_source_name
	;
	l_row_count := sql%rowcount;
	commit;
	pkg_utl_log.log('Deleted: '||l_row_count);
end delete_uploaded_from_src;
