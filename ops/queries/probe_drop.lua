local s=game.surfaces.nauvis
local out={}
local t=s.get_tile(-64,48)
out[#out+1]="tile="..tostring(t and t.name)
for _,e in pairs(s.find_entities_filtered{position={x=-63.7,y=48.65},radius=1.2}) do
  out[#out+1]=e.name.." type="..e.type.." @("..e.position.x..","..e.position.y..")"
end
for _,pos in ipairs({{x=-63.5,y=48.5},{x=-64.5,y=48.5},{x=-63.5,y=49.5},{x=-64,y=48}}) do
  out[#out+1]=string.format("chest %.1f,%.1f=%s",pos.x,pos.y,tostring(s.can_place_entity{name="wooden-chest",position=pos,force=game.forces.player}))
end
return table.concat(out,"\n")
