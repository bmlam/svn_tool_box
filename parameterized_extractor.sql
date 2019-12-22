WITH xform_otypes_ AS (
	SELECT owner, object_name
		,CASE object_type
		WHEN 'PACKAGE' THEN object_type||'_SPEC'
		WHEN 'PACKAGE BODY' THEN REPLACE( object_type, ' ', '_' )
		WHEN 'TYPE'      THEN object_type||'_SPEC'
		WHEN 'TYPE BODY' THEN REPLACE( object_type, ' ', '_' )
		ELSE object_type
		END AS object_type
    FROM all_objects 
)
SELECT object_type, object_name
	,DBMS_METADATA.GET_DDL(object_type=> object_type, name=> object_name, schema=> owner ) ddl
FROM xform_otypes_ o
JOIN TABLE (  split_to_array( :2 ) ) selty ON selty.column_value = o.object_type 
WHERE owner = :1
;
