local t={}
for k,v in pairs(defines.entity_status) do t[#t+1]=k.."="..v end
table.sort(t)
return table.concat(t,", ")
