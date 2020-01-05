--set serveroutput on 
DECLARE
--
/*****  Copyright notes of zip handling code: *******************************
Copyright (C) 2010,2011 by Anton Scheffer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

*****************************************************************************/
-- prerequisite
--create global temporary table temp_blobs ( id number, content blob ) on commit preserve rows;
  type file_list is table of clob;
  g_size_limit integer := power(2, 32);
  g_size_limit_sqlcode integer := -20200;
  g_size_limit_message varchar2(200) := 'Maximum file size of 4GB exceeded';
--
--
  c_LOCAL_FILE_HEADER			constant raw(4) := hextoraw( '504B0304' ); -- Local file header signature
  c_END_OF_CENTRAL_DIRECTORY constant raw(4) := hextoraw( '504B0506' ); -- End of central directory signature
--
-- a very helpful function that should habe been provided in DBMS_STANDARD:
FUNCTION lf_split_to_array ( pi_str VARCHAR2 )
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
END lf_split_to_array;
--
  function blob2num( p_blob blob, p_len integer, p_pos integer )
  return number
  is
	 rv number;
  begin
	 rv := utl_raw.cast_to_binary_integer( dbms_lob.substr( p_blob, p_len, p_pos ), utl_raw.little_endian );
	 if rv < 0
	 then
		rv := rv + 4294967296;
	 end if;
	 return rv;
  end;
--
  function raw2varchar2( p_raw raw, p_encoding varchar2 )
  return varchar2
  is
  begin
	 return coalesce( utl_i18n.raw_to_char( p_raw, p_encoding )
						 , utl_i18n.raw_to_char( p_raw, utl_i18n.map_charset( p_encoding, utl_i18n.GENERIC_CONTEXT, utl_i18n.IANA_TO_ORACLE ) )
						 );
  end;
--
  function little_endian( p_big number, p_bytes pls_integer := 4 )
  return raw
  is
	 t_big number := p_big;
  begin
	 if t_big > 2147483647
	 then
		t_big := t_big - 4294967296;
	 end if;
	 return utl_raw.substr( utl_raw.cast_from_binary_integer( t_big, utl_raw.little_endian ), 1, p_bytes );
  end;
--
  function file2blob
	 ( p_dir varchar2
	 , p_file_name varchar2
	 )
  return blob
  is
	 file_lob bfile;
	 file_blob blob;
  begin
	 file_lob := bfilename( p_dir, p_file_name );
	 dbms_lob.open( file_lob, dbms_lob.file_readonly );
	 dbms_lob.createtemporary( file_blob, true );
	 dbms_lob.loadfromfile( file_blob, file_lob, dbms_lob.lobmaxsize );
	 dbms_lob.close( file_lob );
	 return file_blob;
  exception
	 when others then
		if dbms_lob.isopen( file_lob ) = 1
		then
			dbms_lob.close( file_lob );
		end if;
		if dbms_lob.istemporary( file_blob ) = 1
		then
			dbms_lob.freetemporary( file_blob );
		end if;
		raise;
  end;
--
  function get_file_list
	 ( p_zipped_blob blob
	 , p_encoding varchar2 := null
	 )
  return file_list
  is
	 t_ind integer;
	 t_hd_ind integer;
	 t_rv file_list;
	 t_encoding varchar2(32767);
  begin
	 t_ind := nvl( dbms_lob.getlength( p_zipped_blob ), 0 ) - 21;
	 loop
		exit when t_ind < 1 or dbms_lob.substr( p_zipped_blob, 4, t_ind ) = c_END_OF_CENTRAL_DIRECTORY;
		t_ind := t_ind - 1;
	 end loop;
--
	 if t_ind <= 0
	 then
		return null;
	 end if;
--
	 t_hd_ind := blob2num( p_zipped_blob, 4, t_ind + 16 ) + 1;
	 t_rv := file_list();
	 t_rv.extend( blob2num( p_zipped_blob, 2, t_ind + 10 ) );
	 for i in 1 .. blob2num( p_zipped_blob, 2, t_ind + 8 )
	 loop
		if p_encoding is null
		then
			if utl_raw.bit_and( dbms_lob.substr( p_zipped_blob, 1, t_hd_ind + 9 ), hextoraw( '08' ) ) = hextoraw( '08' )
			then
			 t_encoding := 'AL32UTF8'; -- utf8
			else
			 t_encoding := 'US8PC437'; -- IBM codepage 437
			end if;
		else
			t_encoding := p_encoding;
		end if;
		t_rv( i ) := raw2varchar2
							( dbms_lob.substr( p_zipped_blob
													, blob2num( p_zipped_blob, 2, t_hd_ind + 28 )
													, t_hd_ind + 46
													)
							, t_encoding
							);
		t_hd_ind := t_hd_ind + 46
					 + blob2num( p_zipped_blob, 2, t_hd_ind + 28 )  -- File name length
					 + blob2num( p_zipped_blob, 2, t_hd_ind + 30 )  -- Extra field length
					 + blob2num( p_zipped_blob, 2, t_hd_ind + 32 ); -- File comment length
	 end loop;
--
	 return t_rv;
  end;
--
  function get_file_list
	 ( p_dir varchar2
	 , p_zip_file varchar2
	 , p_encoding varchar2 := null
	 )
  return file_list
  is
  begin
	 return get_file_list( file2blob( p_dir, p_zip_file ), p_encoding );
  end;
--
  function get_file
	 ( p_zipped_blob blob
	 , p_file_name varchar2
	 , p_encoding varchar2 := null
	 )
  return blob
  is
	 t_tmp blob;
	 t_ind integer;
	 t_hd_ind integer;
	 t_fl_ind integer;
	 t_encoding varchar2(32767);
	 t_len integer;
  begin
	 t_ind := nvl( dbms_lob.getlength( p_zipped_blob ), 0 ) - 21;
	 loop
		exit when t_ind < 1 or dbms_lob.substr( p_zipped_blob, 4, t_ind ) = c_END_OF_CENTRAL_DIRECTORY;
		t_ind := t_ind - 1;
	 end loop;
--
	 if t_ind <= 0
	 then
		return null;
	 end if;
--
	 t_hd_ind := blob2num( p_zipped_blob, 4, t_ind + 16 ) + 1;
	 for i in 1 .. blob2num( p_zipped_blob, 2, t_ind + 8 )
	 loop
		if p_encoding is null
		then
			if utl_raw.bit_and( dbms_lob.substr( p_zipped_blob, 1, t_hd_ind + 9 ), hextoraw( '08' ) ) = hextoraw( '08' )
			then
			 t_encoding := 'AL32UTF8'; -- utf8
			else
			 t_encoding := 'US8PC437'; -- IBM codepage 437
			end if;
		else
			t_encoding := p_encoding;
		end if;
		if p_file_name = raw2varchar2
								 ( dbms_lob.substr( p_zipped_blob
														, blob2num( p_zipped_blob, 2, t_hd_ind + 28 )
														, t_hd_ind + 46
														)
								 , t_encoding
								 )
		then
			t_len := blob2num( p_zipped_blob, 4, t_hd_ind + 24 ); -- uncompressed length
			if t_len = 0
			then
			 if substr( p_file_name, -1 ) in ( '/', '\' )
			 then  -- directory/folder
				return null;
			 else -- empty file
				return empty_blob();
			 end if;
			end if;
--
			if dbms_lob.substr( p_zipped_blob, 2, t_hd_ind + 10 ) in ( hextoraw( '0800' ) -- deflate
																						, hextoraw( '0900' ) -- deflate64
																						)
			then
			 t_fl_ind := blob2num( p_zipped_blob, 4, t_hd_ind + 42 );
			 t_tmp := hextoraw( '1F8B0800000000000003' ); -- gzip header
			 dbms_lob.copy( t_tmp
								, p_zipped_blob
								,  blob2num( p_zipped_blob, 4, t_hd_ind + 20 )
								, 11
								, t_fl_ind + 31
								+ blob2num( p_zipped_blob, 2, t_fl_ind + 27 ) -- File name length
								+ blob2num( p_zipped_blob, 2, t_fl_ind + 29 ) -- Extra field length
								);
			 dbms_lob.append( t_tmp, utl_raw.concat( dbms_lob.substr( p_zipped_blob, 4, t_hd_ind + 16 ) -- CRC32
																, little_endian( t_len ) -- uncompressed length
																)
								 );
			 return utl_compress.lz_uncompress( t_tmp );
			end if;
--
			if dbms_lob.substr( p_zipped_blob, 2, t_hd_ind + 10 ) = hextoraw( '0000' ) -- The file is stored (no compression)
			then
			 t_fl_ind := blob2num( p_zipped_blob, 4, t_hd_ind + 42 );
			 dbms_lob.createtemporary( t_tmp, true );
			 dbms_lob.copy( t_tmp
								, p_zipped_blob
								, t_len
								, 1
								, t_fl_ind + 31
								+ blob2num( p_zipped_blob, 2, t_fl_ind + 27 ) -- File name length
								+ blob2num( p_zipped_blob, 2, t_fl_ind + 29 ) -- Extra field length
								);
			 return t_tmp;
			end if;
		end if;
		t_hd_ind := t_hd_ind + 46
					 + blob2num( p_zipped_blob, 2, t_hd_ind + 28 )  -- File name length
					 + blob2num( p_zipped_blob, 2, t_hd_ind + 30 )  -- Extra field length
					 + blob2num( p_zipped_blob, 2, t_hd_ind + 32 ); -- File comment length
	 end loop;
--
	 return null;
  end;
--
  function get_file
	 ( p_dir varchar2
	 , p_zip_file varchar2
	 , p_file_name varchar2
	 , p_encoding varchar2 := null
	 )
  return blob
  is
  begin
	 return get_file( file2blob( p_dir, p_zip_file ), p_file_name, p_encoding );
  end;
--
  procedure add1file
	 ( p_zipped_blob in out nocopy blob
	 , p_name varchar2
	 , p_content blob
	, p_date date default sysdate
	 )
  is
	 t_now timestamp with time zone;
	 t_blob blob;
	 t_len integer;
	 t_clen integer;
	 t_crc32 raw(4) := hextoraw( '00000000' );
	 t_compressed boolean := false;
	 t_name raw(32767);
  begin
	 t_now := cast(nvl(p_date, sysdate) as timestamp with local time zone) at time zone 'UTC';
	 t_len := nvl( dbms_lob.getlength( p_content ), 0 );
	 if t_len > 0
	 then
		t_blob := utl_compress.lz_compress( p_content );
		t_clen := dbms_lob.getlength( t_blob ) - 18;
		t_compressed := t_clen < t_len;
		t_crc32 := dbms_lob.substr( t_blob, 4, t_clen + 11 );
	 end if;
	 if not t_compressed
	 then
		t_clen := t_len;
		t_blob := p_content;
	 end if;
	 if p_zipped_blob is null
	 then
		dbms_lob.createtemporary( p_zipped_blob, true );
	 end if;
	 t_name := utl_i18n.string_to_raw( compose(p_name), 'AL32UTF8' );
	 dbms_lob.append( p_zipped_blob
						 , utl_raw.concat( c_LOCAL_FILE_HEADER -- Local file header signature
												, hextoraw( '1400' )  -- version 2.0
												, case when t_name = utl_i18n.string_to_raw( p_name, 'US8PC437' )
													then hextoraw( '0000' ) -- no General purpose bits
													else hextoraw( '0008' ) -- set Language encoding flag (EFS)
												 end
												, case when t_compressed
													 then hextoraw( '0800' ) -- deflate
													 else hextoraw( '0000' ) -- stored
												 end
												, little_endian( to_number( to_char( t_now, 'ss' ) ) / 2
																	+ to_number( to_char( t_now, 'mi' ) ) * 32
																	+ to_number( to_char( t_now, 'hh24' ) ) * 2048
																	, 2
																	) -- File last modification time
												, little_endian( to_number( to_char( t_now, 'dd' ) )
																	+ to_number( to_char( t_now, 'mm' ) ) * 32
																	+ ( greatest(to_number( to_char( t_now, 'yyyy' ) ) - 1980, 0) ) * 512
																	, 2
																	) -- File last modification date
												, t_crc32 -- CRC-32
												, little_endian( t_clen )							 -- compressed size
												, little_endian( t_len )							  -- uncompressed size
												, little_endian( utl_raw.length( t_name ), 2 ) -- File name length
												, hextoraw( '0000' )									-- Extra field length
												, t_name													-- File name
												)
						 );
	 if t_compressed
	 then
		dbms_lob.copy( p_zipped_blob, t_blob, t_clen, dbms_lob.getlength( p_zipped_blob ) + 1, 11 ); -- compressed content
	 elsif t_clen > 0
	 then
		dbms_lob.copy( p_zipped_blob, t_blob, t_clen, dbms_lob.getlength( p_zipped_blob ) + 1, 1 ); --  content
	 end if;
	 if dbms_lob.istemporary( t_blob ) = 1
	 then
		dbms_lob.freetemporary( t_blob );
	 end if;
	 if g_size_limit < dbms_lob.getlength( p_zipped_blob ) then
	 	raise_application_error (g_size_limit_sqlcode, g_size_limit_message || ' in as_zip.add1file');
	 end if;
  end;
--
  procedure finish_zip( p_zipped_blob in out nocopy blob )
  is
	 t_cnt pls_integer := 0;
	 t_offs integer;
	 t_offs_dir_header integer;
	 t_offs_end_header integer;
	 t_comment raw(32767) := utl_raw.cast_to_raw( 'Implementation by Anton Scheffer, improved by Dirk Strack' );
  begin
	 t_offs_dir_header := dbms_lob.getlength( p_zipped_blob );
	 t_offs := 1;
	 while dbms_lob.substr( p_zipped_blob, utl_raw.length( c_LOCAL_FILE_HEADER ), t_offs ) = c_LOCAL_FILE_HEADER
	 loop
		t_cnt := t_cnt + 1;
		dbms_lob.append( p_zipped_blob
							, utl_raw.concat( hextoraw( '504B0102' )		-- Central directory file header signature
												 , hextoraw( '1400' )			 -- version 2.0
												 , dbms_lob.substr( p_zipped_blob, 26, t_offs + 4 )
												 , hextoraw( '0000' )			 -- File comment length
												 , hextoraw( '0000' )			 -- Disk number where file starts
												 , hextoraw( '0000' )			 -- Internal file attributes =>
																						 --		0000 binary file
																						 --		0100 (ascii)text file
												 , case
														when dbms_lob.substr( p_zipped_blob
																				 , 1
																				 , t_offs + 30 + blob2num( p_zipped_blob, 2, t_offs + 26 ) - 1
																				 ) in ( hextoraw( '2F' ) -- /
																						, hextoraw( '5C' ) -- \
																						)
														then hextoraw( '10000000' ) -- a directory/folder
														else hextoraw( '2000B681' ) -- a file
													end								 -- External file attributes
												 , little_endian( t_offs - 1 ) -- Relative offset of local file header
												 , dbms_lob.substr( p_zipped_blob
																		, blob2num( p_zipped_blob, 2, t_offs + 26 )
																		, t_offs + 30
																		)				-- File name
												 )
							);
		t_offs := t_offs + 30 + blob2num( p_zipped_blob, 4, t_offs + 18 )  -- compressed size
									 + blob2num( p_zipped_blob, 2, t_offs + 26 )  -- File name length
									 + blob2num( p_zipped_blob, 2, t_offs + 28 ); -- Extra field length
	 end loop;
	 t_offs_end_header := dbms_lob.getlength( p_zipped_blob );
	 dbms_lob.append( p_zipped_blob
						 , utl_raw.concat( c_END_OF_CENTRAL_DIRECTORY											-- End of central directory signature
												, hextoraw( '0000' )													 -- Number of this disk
												, hextoraw( '0000' )													 -- Disk where central directory starts
												, little_endian( t_cnt, 2 )											-- Number of central directory records on this disk
												, little_endian( t_cnt, 2 )											-- Total number of central directory records
												, little_endian( t_offs_end_header - t_offs_dir_header )	 -- Size of central directory
												, little_endian( t_offs_dir_header )								-- Offset of start of central directory, relative to start of archive
												, little_endian( nvl( utl_raw.length( t_comment ), 0 ), 2 ) -- ZIP file comment length
												, t_comment
												)
						 );
	 if g_size_limit < dbms_lob.getlength( p_zipped_blob ) then
	 	raise_application_error (g_size_limit_sqlcode, g_size_limit_message || ' in as_zip.finish_zip');
	 end if;
  end;
--
  procedure save_zip
	 ( p_zipped_blob blob
	 , p_dir varchar2 := 'MY_DIR'
	 , p_filename varchar2 := 'my.zip'
	 )
  is
	 t_fh utl_file.file_type;
	 t_len pls_integer := 32767;
  begin
	 t_fh := utl_file.fopen( p_dir, p_filename, 'wb' );
	 for i in 0 .. trunc( ( dbms_lob.getlength( p_zipped_blob ) - 1 ) / t_len )
	 loop
		utl_file.put_raw( t_fh, dbms_lob.substr( p_zipped_blob, t_len, i * t_len + 1 ) );
	 end loop;
	 utl_file.fclose( t_fh );
  end;
--

begin -- main 
	declare
		g_zipped_blob blob;
        lt_owner  		ora_mining_varchar2_nt ; 
        lt_object_type 	ora_mining_varchar2_nt ; 
	begin
        lt_owner 		:= lf_split_to_array( :1 );
        lt_object_type 	:= lf_split_to_array( :2 );
        
		FOR ddl_rec IN (
			-- try not to edit this query but rather modify it as an SQL file so it is easier to test the changed made 
			-- without testing this whole script!
			-- 
			WITH xform_otypes_ AS (
				SELECT owner, object_name
					,CASE object_type
					WHEN 'PACKAGE'      THEN object_type||'_SPEC'
					WHEN 'PACKAGE BODY' THEN REPLACE( object_type, ' ', '_' )
					WHEN 'TYPE'         THEN object_type||'_SPEC'
					WHEN 'TYPE BODY'    THEN REPLACE( object_type, ' ', '_' )
					ELSE object_type
					END AS object_type
					,CASE object_type
					WHEN 'FUNCTION'     THEN 'FN'
					WHEN 'PACKAGE'      THEN 'PKS'
					WHEN 'PACKAGE BODY' THEN 'PKB'
					WHEN 'PROCEDURE'    THEN 'PRC'
					WHEN 'TRIGGER'      THEN 'TRG'
					WHEN 'TYPE'         THEN 'TPS'
					WHEN 'TYPE BODY'    THEN 'TPB'
					WHEN 'VIEW'         THEN 'VW'
					ELSE 'SQL'
					END AS file_ext
			        , owner||'/'||INITCAP(replace(object_type,' BODY')||'s' ) subdir
			    FROM /*replace_start*/ all_objects /*replace_end*/ o
				JOIN TABLE (  lt_owner ) selow ON selow.column_value = o.owner
				WHERE NOT object_name like '%$$%' -- exclude system gerated objects
				  AND NOT object_name like 'BIN$%' -- exclude stuff in recycle bin 
			)
			SELECT object_type, object_name, subdir
			    , subdir||'/'||object_name||'.'||file_ext script_path
			    , ROW_NUMBER() OVER (PARTITION BY subdir ORDER BY object_type, object_name ) seq_in_dir
				,DBMS_METADATA.GET_DDL(object_type=> object_type, name=> object_name, schema=> owner ) ddl
			FROM xform_otypes_ o
			JOIN TABLE (  lt_object_type ) selty ON selty.column_value = o.object_type 
            ORDER BY OWNER, object_type, object_name
			-- 
		) LOOP
			IF ddl_rec.seq_in_dir = 1 THEN
				add1file( g_zipped_blob, ddl_rec.subdir||'/', null ); -- add folder
			END IF; -- create subdir
				
			DECLARE
				l_warning NUMBER;
				l_src_offset NUMBER(38) := 1;
				l_dest_offset NUMBER(38) := 1;
				l_lob_len  NUMBER(38); 
				l_zip_part_blob  BLOB;
				l_lang_context  NUMBER(38) := dbms_lob.default_lang_ctx;
                l_ddl CLOB;
			BEGIN
				dbms_lob.createtemporary( l_zip_part_blob, true );
                l_ddl := ddl_rec.ddl ||chr(10)||'/'||chr(10); -- make script runnable in SQLPLUS 
				l_lob_len :=  dbms_lob.getlength( l_ddl );
                dbms_output.put_line( 'Ln'||$$plsql_line||' lob len: '||l_lob_len );
				dbms_lob.converttoblob(
				  dest_lob       => l_zip_part_blob
				  ,src_clob       =>        l_ddl 
				  ,amount         =>        l_lob_len
				  ,dest_offset    =>	l_dest_offset
				  ,src_offset     =>	l_src_offset
				  ,blob_csid      =>    DBMS_LOB.DEFAULT_CSID 
				  ,lang_context   =>	l_lang_context
				  ,warning        =>        l_warning
				); 
				IF l_warning > 0 THEN 
					RAISE_application_error( 20001, 'Got warning '||l_warning||' for '||ddl_rec.script_path );
				END IF; -- CHECK warning	
                dbms_output.put_line( 'Ln'||$$plsql_line||' '||dbms_lob.getlength( l_zip_part_blob ) );
				add1file( g_zipped_blob, ddl_rec.script_path, l_zip_part_blob );

				dbms_lob.freetemporary( l_zip_part_blob );
			END add_file_to_zip;
		END LOOP ; -- over ddl scripts

		finish_zip( g_zipped_blob );
		-- save_zip( g_zipped_blob, 'MY_DIR', 'my.zip' );
		 dbms_output.put_line( 'Ln'||$$plsql_line||': '|| dbms_LOB.getlength ( g_zipped_blob ) );
		
		if true then 
			delete temp_blobs;
			insert into temp_blobs ( content ) values ( g_zipped_blob );
			commit;
		end if;

		dbms_lob.freetemporary( g_zipped_blob );
	end;
	--

end; --main 

