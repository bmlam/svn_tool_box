CREATE OR REPLACE EDITIONABLE PACKAGE BODY "EDWH_TNSPARSER"."PKG_PARSE_TNS"
AS
   /**
    * $Author: Lam.Bon-Minh $
    * $HeadURL: https://bic-svn.viola.local/repo/BIC-repo/dba/admin/tns_names_central/dwso/tnsparser/packages/pkg_parse_tns/pkg_parse_tns-def.sql $
    */

   c_spec_url       CONSTANT VARCHAR2 (1024) := '$HeadURL: https://bic-svn.viola.local/repo/BIC-repo/dba/admin/tns_names_central/dwso/tnsparser/packages/pkg_parse_tns/pkg_parse_tns-def.sql $';
   c_body_version            VARCHAR2 (1024);
   /**
    */
   c_body_url                VARCHAR2 (1024);
  gc_token_type_comma constant token_type := ',';

procedure debug (
p_text varchar2
) as
begin
	pkg_utl_log.log( p_text, null, /*p_prio => */pkg_utl_log.gc_debug);
end debug;
*/ 
/** * Package initialization */
BEGIN
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := gc_simple_keyword_xpcxtmo  ;
END;

