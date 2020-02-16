CREATE OR REPLACE procedure foo (
) as
/*	-- will this cause a bug?	*/
begin
	a := q{"bala ' blu (()) '; what ever comes will ( comes 
the q literal contains new lines!!
huhu} "}
	;
	g_simple_attribute_keywords( (g_simple_attribute_keywords.count+1) ):= 'TDU';
	a := case when 1=1 then 0 else 2 end;
	case when 1=1 then b := 2 when 2=0 then b:=  33; end case;
	for i in 1 .. 3 loop null; 
	end loop;
end foo;
