local p=prototypes.entity["small-electric-pole"]
local out={}
for _,k in ipairs({"supply_area_distance","max_wire_distance","wire_reach","maximum_wire_distance"}) do
  local ok,v=pcall(function() return p[k] end)
  out[#out+1]=k.."="..tostring(ok)..":"..tostring(v)
end
return table.concat(out,"\n")
