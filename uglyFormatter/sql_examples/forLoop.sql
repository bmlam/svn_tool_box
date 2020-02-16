create procedure foo as
begin 
-- line comment
	for i in reverse 1 .. 3 loop
		if length(  chr(9)/*tab*/||chr(10) ) = 0 /* nothing left after removal of whitespaces*/
		then
			l_exclude_trailing_blank_lines := l_exclude_trailing_blank_lines + 1;
		else
			exit;
		end if;
	end loop;
end;

