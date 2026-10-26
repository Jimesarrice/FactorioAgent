local s=game.surfaces.nauvis
local out={}
for _,e in pairs(s.find_entities_filtered{type="container",force="player"}) do
  local parts={}
  for i=1,3 do
    local inv=e.get_inventory(i)
    if inv then
      for _,c in pairs(inv.get_contents()) do parts[#parts+1]=c.name.."x"..c.count end
    end
  end
  out[#out+1]=string.format("#%s @(%.1f,%.1f) %s",tostring(e.unit_number),e.position.x,e.position.y,table.concat(parts,","))
end
return table.concat(out,"\n")
