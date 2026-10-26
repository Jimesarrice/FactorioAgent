local s = game.surfaces.nauvis
local pts = {{37.5,30.5},{31.5,33.5},{25.5,36.5},{19.5,39.5},{13.5,42.5},{7.5,45.5},{1.5,48.5},{-4.5,51.5},{-10.5,55.5}}
local lines = {}
for _, p in ipairs(pts) do
  local ok = s.can_place_entity{name="small-electric-pole", position={x=p[1],y=p[2]}, force=game.forces.player}
  local es = s.find_entities_filtered{area={{p[1]-0.6,p[2]-0.6},{p[1]+0.6,p[2]+0.6}}}
  local names = {}
  for _, e in pairs(es) do names[#names+1] = e.name end
  lines[#lines+1] = string.format("%.1f,%.1f can=%s near=%s", p[1], p[2], tostring(ok), table.concat(names,","))
end
return table.concat(lines,"\n")
