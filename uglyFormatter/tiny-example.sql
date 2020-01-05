
CREATE OR REPLACE EDITIONABLE PACKAGE BODY "EDWH_TNSPARSER"."PKG_PARSE_TNS"
AS
   /**
    * $Author: Lam.Bon-Minh $
    * $HeadURL: https://bic-svn.viola.local/repo/BIC-repo/dba/admin/tns_names_central/dwso/tnsparser/packages/pkg_parse_tns/pkg_parse_tns-def.sql $
    */

   /** * Package spec version string.  */
   c_spec_version   CONSTANT VARCHAR2 (1024) := '$Id: pkg_parse_tns-def.sql 26969 2016-09-27 15:05:24Z Lam.Bon-Minh $';
   c_body_version            VARCHAR2 (1024);

function clob_2_token_table 
return tns_entry_token_table ;

--    * $Id: pkg_parse_tns-impl.sql 26969 2016-09-27 15:05:24Z Lam.Bon-Minh $
--    * $HeadURL: https://bic-svn.viola.local/repo/BIC-repo/dba/admin/tns_names_central/dwso/tnsparser/packages/pkg_parse_tns/pkg_parse_tns-impl.sql $
--    */
--

/***********************************************************************************/
procedure delete_uploaded_from_src (
	p_source_name varchar2, p_clob clob 
)
/***********************************************************************************/
as
	l_row_count integer;
begin
	pkg_utl_log.log('Deleting entry from source: '
		||p_source_name||' user: '||nvl( v('APP_USER'), user) );
	--
	delete from tns_entry_uploaded
	where file_source = p_source_name
	;
	l_row_count := sql%rowcount;
	commit;
	pkg_utl_log.log('Deleted: '||l_row_count);
end delete_uploaded_from_src;


/**
 * Package initialization
 */
BEGIN
   c_body_version    := '$Id: pkg_parse_tns-impl.sql 26969 2016-09-27 15:05:24Z Lam.Bon-Minh $';
   -- if we do not expect to refer to a keyword literal more than once in this package, we do not need to use a constant.
   -- but do observe the alphabetical order for better debugging
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := gc_simple_keyword_cxtmo    ;
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := 'TDU'                      ;
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := gc_simple_keyword_xpcxtmo  ;

END;

