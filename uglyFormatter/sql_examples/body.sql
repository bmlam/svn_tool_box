begin
	case a = 1 then b := 2 else b:= 3; end case;
	select 2 into l_row_count
	from schemaA.table_b@db_link.com alias_2;
end ;

