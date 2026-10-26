local out={}
local g=game.get_entity_by_unit_number(126)
if not g then return "generator126 missing" end
out[#out+1]="gen surface="..g.surface.name.." force="..g.force.name.." pos="..g.position.x..","..g.position.y
local s=g.surface
local area={{g.position.x-16,g.position.y-16},{g.position.x+16,g.position.y+16}}
for _,e in pairs(s.find_entities_filtered{area=area}) do
  if e.type~="tree" and e.type~="simple-entity" then
    out[#out+1]=string.format("%s#%s(%s) @(%.1f,%.1f) d=%s st=%s",e.type,e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status))
  end
end
return table.concat(out,"\n")
