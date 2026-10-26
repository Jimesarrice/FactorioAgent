local s=game.surfaces.nauvis
local t=s.get_tile(-5,52)
local out={"tile="..tostring(t and t.name)}
for _,e in pairs(s.find_entities_filtered{position={x=-4.5,y=52.5},radius=1.0}) do
  out[#out+1]=e.name.." type="..e.type.." @("..e.position.x..","..e.position.y..")"
end
out[#out+1]="can chest="..tostring(s.can_place_entity{name="wooden-chest",position={x=-4.5,y=52.5},force=game.forces.player})
out[#out+1]="can chest2="..tostring(s.can_place_entity{name="wooden-chest",position={x=-3.5,y=52.5},force=game.forces.player})
return table.concat(out,"\n")
