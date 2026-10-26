local s=game.surfaces.nauvis
local out={}
for _,u in ipairs({217,218,219}) do
  local e
  for _,c in pairs(s.find_entities_filtered{type="mining-drill",force="player"}) do if c.unit_number==u then e=c end end
  if e then
    local ma=e.mining_area
    local counts={}
    for _,r in pairs(s.find_entities_filtered{area=ma,type="resource"}) do counts[r.name]=(counts[r.name] or 0)+r.amount end
    local parts={}; for n,a in pairs(counts) do parts[#parts+1]=n.."="..a end
    local line1=e.surface.find_entities_filtered{position=e.drop_position,radius=0.4,type="transport-belt"}
    out[#out+1]=string.format("#%d status=%s drop=(%.1f,%.1f) belts=%d res=%s",u,tostring(e.status),e.drop_position.x,e.drop_position.y,#line1,table.concat(parts,","))
  end
end
return table.concat(out,"\n")
