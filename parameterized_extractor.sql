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
					ELSE '.SQL'
					END AS file_ext
			        , owner||'/'||INITCAP(replace(object_type,' BODY')||'s' ) subdir
			    FROM all_objects 
			)
			SELECT object_type, object_name, subdir
			    , subdir||'/'||object_name||'.'||file_ext script_path
			    , ROW_NUMBER() OVER (PARTITION BY subdir ORDER BY object_type, object_name ) seq_in_dir
				,DBMS_METADATA.GET_DDL(object_type=> object_type, name=> object_name, schema=> owner ) ddl
			FROM xform_otypes_ o
			JOIN TABLE (  split_to_array( :2 ) ) selty ON selty.column_value = o.object_type 
			WHERE owner = :1
            ORDER BY OWNER, object_type, object_name
;
