
CREATE OR REPLACE EDITIONABLE PACKAGE BODY "EDWH_TNSPARSER"."PKG_PARSE_TNS"
AS
   /**
    * $Author: Lam.Bon-Minh $
    * $HeadURL: https://bic-svn.viola.local/repo/BIC-repo/dba/admin/tns_names_central/dwso/tnsparser/packages/pkg_parse_tns/pkg_parse_tns-def.sql $
    */

   /**
    * Package spec version string.
    */
   c_spec_version   CONSTANT VARCHAR2 (1024) := '$Id: pkg_parse_tns-def.sql 26969 2016-09-27 15:05:24Z Lam.Bon-Minh $';
   c_spec_url       CONSTANT VARCHAR2 (1024) := '$HeadURL: https://bic-svn.viola.local/repo/BIC-repo/dba/admin/tns_names_central/dwso/tnsparser/packages/pkg_parse_tns/pkg_parse_tns-def.sql $';
   c_body_version            VARCHAR2 (1024);
   /**
    */
   c_body_url                VARCHAR2 (1024);

procedure insert_tns_file_entries
(  p_file_content in  clob
  ,p_file_origin_host varchar2
  ,p_use_upload_id    integer default null /* in case the file content has been saved in a separate step into TNS_FILE_UPLOAD,
  all the above parameters must be null. The relevant data will be retrieved from TNS_FILE_UPLOAD
  */
);

function clob_2_token_table
( p_clob clob
) return tns_entry_token_table
;

-- When this procedure has executed successfully, all tables which are populated by the parser
-- should be empty. If not, we have not understood the data model or the procedure is faulty
procedure cleanup_parser_output
;

procedure elect_primary_entry (
	p_for_entry_name IN OUT varchar2 -- if null, election is applied to all names. Automatic algorithm will be applied
) ;

function validate_bulk_elect_primary ( -- we primary want to check that no entry name is selected more than once
	p_tab_entry_id dbms_utility.number_array
) return varchar2;


procedure bulk_discard_entry (
	p_tab_entry_id dbms_utility.number_array
);

/***********************************************************************************/
function enrich_with_non_primary (
	p_tab_entry_id dbms_utility.number_array
) return dbms_utility.number_array
/* The input array contains entries with primary flag set to true.
* This function enriches the input array with entries which have the same
* entry names but with primary flag set to false
*/
;
procedure delete_uploaded_from_src 
;

   /**
    * $Author: Lam.Bon-Minh $
    * $Date: 2016-09-27 17:05:24 +0200 (Di, 27 Sep 2016) $
    * $Revision: 26969 $
    * $Id: pkg_parse_tns-impl.sql 26969 2016-09-27 15:05:24Z Lam.Bon-Minh $
    * $HeadURL: https://bic-svn.viola.local/repo/BIC-repo/dba/admin/tns_names_central/dwso/tnsparser/packages/pkg_parse_tns/pkg_parse_tns-impl.sql $
    */

/*
The information in TNSNAMES.ORA, or more precisely, each entry in the file will be parsed using this strategy:

The content will be converted to a cross reference which contains the line number and column position for each token.
A token is one of the following:
	+ any punctation mark except minus sign, underscore and ampersand
	+ any other special characters, namely single quote, double quote, equal sign, left and right parenthesis, left and right arrow, left and right curly bracket
	+ hash sign, which at the beginning of a line will be interpreted as the start of a comment line
	+ word: a string of alphanumeric characters, but also minus sign, underscore and ampersand, enclosing single or double quotes

All whitespace characters are removed from the cross reference.

After the tokenizing process, a little finite state machine kicks in:

*/
/*
  c_nl constant char := chr(10);

  type t_name_to_int is table of integer index by varchar2(200);

  subtype word_type is varchar2(100);
  type key_value_pair_list is table of varchar2(100) index by varchar2(50);
  type word_stack is table of word_type index by binary_integer;

  subtype token_type is varchar2(1);

  gc_token_type_lpar  constant token_type := '(';
  gc_token_type_rpar  constant token_type := ')';
  gc_token_type_eqsn  constant token_type := '=';
  gc_token_type_word  constant token_type := 'w';
  gc_token_type_comnt constant token_type := '/';
  gc_token_type_comma constant token_type := ',';

  -- keywords in an TNS entry which introduces an attribute with complex value
	gc_complex_keyword_entrname  constant word_type := 'ENTRY_NAME'; -- this is a virtual keyword, virtual as no such keyword exists
	gc_simple_keyword_type      constant word_type := 'TYPE'; -- actually CONNECT_DATA.FAILOVER_MODE.TYPE ! We hope this keyword is not used anywhere else!
	--
	g_simple_attribute_keywords dbms_utility.lname_array;
	--
procedure debug (
p_text varchar2
) as
begin
	pkg_utl_log.log( p_text, null, /*p_prio => */pkg_utl_log.gc_debug);
end debug;
*/ 
-- bla bla /* abala */
procedure tokenize_tnsnames_file
(  p_file_lines dbms_utility.lname_array
  ,p_token_table out tns_entry_token_table
)
as
	l_line varchar2(4000);
	l_line_no integer := 0;
	l_token_table tns_entry_token_table := tns_entry_token_table();
	l_exclude_trailing_blank_lines integer := 0;
/*
	procedure i$add_token
	(  p_fsm_input_type token_type
      ,p_token_literal  varchar2 default null
      ,p_line_no        integer
      ,p_column_pos     integer default 1
	)	as
		l_token tns_entry_token ;
	begin
		l_token := tns_entry_token (
			fsm_input_type  => p_fsm_input_type
			, token_literal => p_token_literal
			, line_no       => p_line_no
			, column_pos    => p_column_pos
		);
		l_token_table.extend();
		l_token_table(l_token_table.count) := l_token;
		debug( 'Line '||$$plsql_line||' token at '||p_line_no||'/'||p_column_pos||' is '|| p_fsm_input_type) ;
	end i$add_token ;
*/ 
--
begin
	-- we have problem with trailing lines which contain only whitespace characters
	-- if such lines are present, exclude them from processing
	for i in reverse 1 .. p_file_lines.count loop
		if length( translate( p_file_lines(i), chr(9)/*tab*/||chr(10)||' ', '' ) ) = 0 /* nothing left after removal of whitespaces*/
		then
			l_exclude_trailing_blank_lines := l_exclude_trailing_blank_lines + 1;
		else
			exit;
		end if;
	end loop;
	--
	for i in 1 .. p_file_lines.count - l_exclude_trailing_blank_lines loop
		l_line := p_file_lines(i);
		l_line_no := l_line_no + 1;
		-- check for comment line
		if regexp_like ( l_line, '^\s*#.*') then
			i$add_token
			(  p_fsm_input_type => gc_token_type_comnt
			  ,p_token_literal  => l_line
			  ,p_line_no        => l_line_no
			);
		else
			l_line_len := length( l_line );
			l_scan_pos := 1;
			debug( 'Line '||$$plsql_line||' parsing line '||l_line_no||' with len '||l_line_len) ;
			while l_scan_pos <= l_line_len loop
				l_non_ws_pos := regexp_instr( l_line, '[^[:blank:][:cntrl:]]', l_scan_pos ); /* tab is for Oracle a control character!*/
				/* when the file content is entered in an APEX GUI text area, the last line may not have a line break.
				* In this case, the regexp_instr() will return 0, which is wrong. We need to catch that situation
				* and override the position variable
				*/
				debug( 'Line '||$$plsql_line||' l_scan_pos '||l_scan_pos||' l_non_ws_pos '||l_non_ws_pos) ;
				if l_non_ws_pos = 0
				  and l_line_no = p_file_lines.count and l_scan_pos = length(l_line)
				then
					l_non_ws_pos := l_scan_pos;
				end if;
				if l_non_ws_pos = 0 then
					-- no more non-whitespace found
					exit; -- we are done with this line
				end if;
				l_fsm_input_type := null; -- re-init
				debug( 'Line '||$$plsql_line||' l_non_ws_pos '||l_non_ws_pos ||' char '||substr(l_line, l_non_ws_pos, 1) );
				l_fsm_input_type :=
					case substr(l_line, l_non_ws_pos, 1)
					when '(' then gc_token_type_lpar
					when ')' then gc_token_type_rpar
					when '=' then gc_token_type_eqsn
					when ',' then gc_token_type_comma
					end ;
					debug( 'Line '||$$plsql_line||'fms input='||l_fsm_input_type);
				if l_fsm_input_type is not null then
					i$add_token
					(  p_fsm_input_type => l_fsm_input_type
					  ,p_token_literal  => null
					  ,p_line_no        => l_line_no
					  ,p_column_pos     => l_non_ws_pos
					);
					l_scan_pos := l_non_ws_pos + 1;
					continue;
				end if;
				--  word or trailing commment?
				-- intercept comments after a token (trailing comment)
				if substr(l_line, l_non_ws_pos, 1) = '#' then
					exit; -- we are done with this line
				end if; -- trailing comment
				-- now it must be a word
				l_word := regexp_substr( l_line, '[+]{0,1}[[:alnum:]-_.@]+', l_non_ws_pos);
				debug( 'Line '||$$plsql_line||' l_word is '||l_word);
				if l_word is null then
					raise_application_error(-20001, 'At line '||l_line_no||' from position '||l_scan_pos
						||': expecting an identifier but found: '||substr(l_line, l_scan_pos) );
				end if; -- against all hope token is not a word (identifier)
				l_fsm_input_type := gc_token_type_word ;
				i$add_token
				(  p_fsm_input_type => l_fsm_input_type
				  ,p_token_literal  => l_word
				  ,p_line_no        => l_line_no
				  ,p_column_pos     => l_non_ws_pos
				);
			end loop; -- over single line
		end if; -- check for comment line
	end loop; -- over lines
	p_token_table := l_token_table;
exception
	when others then
		pkg_Utl_log.log( DBMS_UTILITY.FORMAT_ERROR_BACKTRACE, null, pkg_utl_log.gc_error);
		raise;
end tokenize_tnsnames_file;

function clob_2_token_table
( p_clob clob
) return tns_entry_token_table
as
	l_line_array dbms_utility.lname_array;
    l_token_table tns_entry_token_table;
begin
	pkg_utl_tns.clob_2_line_array (  p_clob => p_clob
		,p_line_array => l_line_array
	);
	tokenize_tnsnames_file
	(  p_file_lines => l_line_array
	  ,p_token_table => l_token_table
	);
	return l_token_table;
end clob_2_token_table ;

procedure insert_tns_file_entries
(  p_file_content in  clob
  ,p_file_origin_host varchar2
  ,p_file_origin_path varchar2
  ,p_file_upload_remarks varchar2
  ,p_use_upload_id    integer default null
)
as
	l_file_content    clob;
	l_upload_id       integer;
	l_index_for_debug integer;
	l_line_array dbms_utility.lname_array;
	l_token_table tns_entry_token_table ;
	subtype fsm_state_subtype is varchar2(50);
	--
	c_fsm_initial           constant fsm_state_subtype := 'initial';
	l_kvp_array_current         key_value_pair_list;

	c_kvp_array_id_desc_list    constant integer := 6;
	--
	l_entry_comment_array dbms_utility.lname_array;
	--
	l_stack_tns_name   vchar100_stack_25 := vchar100_stack_25();
	l_cached_attr_value word_type;
	l_fsm_state   fsm_state_subtype := c_fsm_initial;
	--
	l_stack_addr_id 		int_stack_25 := int_stack_25();
	--
	function peek_keyword return word_type
	as
	begin
		if l_keyword_stack.count > 0 then
		  return l_keyword_stack( l_keyword_stack.count );
		else
		  return null;
		end if;
	end peek_keyword;


	  procedure move_curr_kvp_array_to (p_array_id integer)
	  -- when we hit a new complex keyword, the key value pairs we have cached so far
	  -- in the current (default) array need to be relocated so they will not be mixed
	  -- up. For example, the KV pairs for ADDRESS_LIST are cached initially in the
	  -- default array, then ADDRESS is encountered, we need to move the cached KV pairs
	  -- to the array for ADDRESS_LIST.
	  as
		k word_type;
	  begin
		debug( 'Line '||$$plsql_line||': p_array_id '||p_array_id ||' count '||l_kvp_array_current.count );
		case p_array_id
		when c_kvp_array_id_desc_list then
			k := l_kvp_array_current.first;
			while k is not null loop
				l_kvp_array_desc_list(k) := l_kvp_array_current(k);
				l_kvp_array_current.delete( k );
				k := l_kvp_array_current.next (k);
			end loop;
		when c_kvp_array_id_cx_data then
			k := l_kvp_array_current.first;
			while k is not null loop
				l_kvp_array_cx_data(k) := l_kvp_array_current(k);
				l_kvp_array_current.delete( k );
				k := l_kvp_array_current.next (k);
			end loop;
			-- reset_kvp_array( c_kvp_array_id_current);
		else
			raise_application_error( -20001, 'Key value pair array id invalid:  "'||p_array_id||'!');
		end case;
	exception
		when others then
			pkg_Utl_log.log( DBMS_UTILITY.FORMAT_ERROR_BACKTRACE, null, pkg_utl_log.gc_error);
			raise;
	end move_curr_kvp_array_to;
	--
	--
	procedure persist_tns_addr_list
	as
	/* we will construct an INSERT statement dynamically for tns_addr_list and execute it.
	* See also comments in PERSIST_TNS_DESCRIPTION regarding handling of column names and values during the construction.
	* The id of the tns_addr_list entry is
	*/
		l_entity_id integer;
		l_child_seq integer;
		l_attribute_name     word_type;
		l_column_name_to_use varchar2(30);
	begin
		debug( 'Line '||$$plsql_line||': persisting ADDRESS_LIST');
		--
		-- process ADDRESS_LIST attributes
		--
		move_curr_kvp_array_to ( c_kvp_array_id_addr_list ); /* merge all current attributes to the proper queue.
		This way we only need to loop thru only one queue
		*/
		l_attribute_name := l_kvp_array_addr_list.first;
		while l_attribute_name is not null loop
			debug( 'Line '||$$plsql_line||': l_attribute_name is '||l_attribute_name);
			l_column_name_to_use := l_attribute_name; -- hope this is always ok despite column name length limitation
			l_attribute_name := l_kvp_array_addr_list.next (l_attribute_name);
			l_kvp_array_addr_list.delete( l_attribute_name_old );
			--debug( 'Line '||$$plsql_line||': count '||l_kvp_array_addr_list.count);
		end loop;
		--
		-- construct INSERT statement
		--
		l_entity_id := tns_shared_seq.nextval;
		l_columns(l_columns.count + 1) := 'ID';
		l_values (l_values.count + 1) := l_entity_id;
		for i in 1 .. l_columns.count loop
			l_column_str := case when i > 1 then l_column_str ||', '  end
				|| l_columns(i)
				;
			for i in 1 .. l_values.count loop
				l_value_str := case when i > 1 then l_value_str ||', '  end
				||l_values(i);
			end loop;
		end loop;
		l_dml := 'insert into tns_addr_list('
			||l_column_str||c_nl
			||') values ('||l_value_str	||')'
			;
		--
		begin
			execute immediate l_dml;
		exception
			when others then
				raise_application_error( -20001, sqlerrm||c_nl||l_dml);
		end try_insert;
		-- Link ADDRESS_LIST and ADDRESS
		while not l_stack_addr_id.empty loop
			l_child_seq := l_stack_addr_id.position;
			l_stack_addr_id.pop ( l_addr_id );
			insert into tns_addr_x_addr_list ( addr_list_id, address_id,  seq )
			values                          ( l_entity_id,  l_addr_id, l_child_seq)
			;
		end loop;
	exception
		when others then
			pkg_Utl_log.log( DBMS_UTILITY.FORMAT_ERROR_BACKTRACE, null, pkg_utl_log.gc_error);
			raise;
	end persist_tns_addr_list;
	--

/***********************************************************************************/
procedure merge_to_uploaded_entries (
	p_entry_id integer default null
)
/***********************************************************************************/
as
begin
	--
	merge into tns_entry_uploaded tgt
	using (
		with rawdata as (
			select entry_name
			  , trim( lower(tns_file_origin_host ) ) as file_source
			  , load_dt as last_load_dt
			  , nvl( v('APP_USER'), user ) as loaded_by_user
			  , addr_host as cx_data_host_addr_1
			  , addr_port as cx_data_port_1
			  , dbms_lob.substr(entry_comments, 200 ) as entry_comments
			  , description_list_clause as tns_definition
			  , id as entry_id
			from v_tns_entry_generator
			where 1=1
			  and ( p_entry_id is null or id = p_entry_id )
		) , agg as ( -- we need to dedupicate because the same entry name may occur more than once in the same tnsnames.ora
			select t.*
				,row_number() over ( partition by entry_name, file_source order by entry_id ) as dedupe
			from rawdata t
		)
		select 	entry_name, file_source
		, entry_comments, tns_definition
		, cx_data_host_addr_1, cx_data_port_1
		, loaded_by_user, last_load_dt
		from agg
		where dedupe = 1	) src
	on ( tgt.entry_name = src.entry_name
		and tgt.file_source = src.file_source )
	when matched then update
	set TNS_DEFINITION        = src.tns_definition
	   ,entry_comments        = src.entry_comments
	   ,last_load_dt          = src.last_load_dt
	   ,cx_data_host_addr_1   = src.cx_data_host_addr_1
	   ,cx_data_port_1        = src.cx_data_port_1
	   ,loaded_by_user        = src.loaded_by_user
	when not matched then
	insert ( id
	, entry_name, file_source
	, entry_comments, tns_definition
	, cx_data_host_addr_1, cx_data_port_1
	, loaded_by_user, last_load_dt
	)
	values ( tns_shared_seq.nextval
	, src.entry_name, src.file_source
	, src.entry_comments, src.tns_definition
	, src.cx_data_host_addr_1, src.cx_data_port_1
	, src.loaded_by_user, src.last_load_dt
	)
	;
	commit;
end merge_to_uploaded_entries;

/***********************************************************************************/
procedure delete_uploaded_from_src (
	p_source_name varchar2
)
/***********************************************************************************/
as
	l_row_count integer;
begin
	pkg_utl_log.log('Deleting entry from source: '||p_source_name||' user: '||nvl( v('APP_USER'), user) );
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
   c_body_url        := '$HeadURL: https://bic-svn.viola.local/repo/BIC-repo/dba/admin/tns_names_central/dwso/tnsparser/packages/pkg_parse_tns/pkg_parse_tns-impl.sql $';
   -- if we do not expect to refer to a keyword literal more than once in this package, we do not need to use a constant.
   -- but do observe the alphabetical order for better debugging
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := gc_simple_keyword_cxtmo    ;
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := 'HS'                       ;
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := gc_simple_keyword_sid      ;
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := gc_simple_keyword_src_rout ;
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := 'TDU'                      ;
   g_simple_attribute_keywords(g_simple_attribute_keywords.count+1) := gc_simple_keyword_xpcxtmo  ;

END;

