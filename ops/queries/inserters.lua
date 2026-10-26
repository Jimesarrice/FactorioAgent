local s=game.surfaces.nauvis
local out={}
for _,e in pairs(s.find_entities_filtered{type="inserter",force="player"}) do
  if e.unit_number==118 or e.unit_number==119 or e.unit_number==146 then
    local ok1,p=pcall(function() return e.pickup_position end)
    local ok2,d=pcall(function() return e.drop_position end)
    out[#out+1]=string.format("#%s @(%.1f,%.1f) dir=%s status=%s pickup=%s drop=%s",
      tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),tostring(e.status),
      ok1 and string.format("(%.1f,%.1f)",p.x,p.y) or "?",
      ok2 and string.format("(%.1f,%.1f)",d.x,d.y) or "?")
  end
end
return table.concat(out,"\n")
