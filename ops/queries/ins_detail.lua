local s=game.surfaces.nauvis
local t={}
for _,u in ipairs({534,775,457}) do
  local e
  for _,x in pairs(s.find_entities_filtered{type="inserter"}) do if x.unit_number==u then e=x break end end
  if e then
    local p={}
    local maxi=e.get_max_inventory_index()
    for i=1,maxi do local inv=e.get_inventory(i) if inv then for _,it in pairs(inv.get_contents()) do p[#p+1]=it.name.."x"..it.count end end end
    t[#t+1]=string.format("#%s @(%.1f,%.1f) d=%s st=%s pickup=(%.1f,%.1f) drop=(%.1f,%.1f) held[%s]",tostring(u),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),e.pickup_position.x,e.pickup_position.y,e.drop_position.x,e.drop_position.y,table.concat(p,","))
  else t[#t+1]="missing "..u end
end
return table.concat(t,"\n")
