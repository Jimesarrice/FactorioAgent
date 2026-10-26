local s=game.surfaces.nauvis
local items={
 {"small-electric-pole",-4.5,56.5,0},
 {"small-electric-pole",1.5,56.5,0},
 {"small-electric-pole",7.5,56.5,0},
 {"small-electric-pole",13.5,56.5,0},
 {"small-electric-pole",18.5,57.5,0},
 {"small-electric-pole",18.5,62.5,0},
}
local lines={}
for _,it in ipairs(items) do
  local name,x,y,d=it[1],it[2],it[3],it[4]
  local ok=s.can_place_entity{name=name,position={x=x,y=y},direction=d,force=game.forces.player}
  local es=s.find_entities_filtered{area={{x-0.6,y-0.6},{x+0.6,y+0.6}}}
  local names={}
  for _,e in pairs(es) do names[#names+1]=e.name end
  lines[#lines+1]=string.format("%s (%.1f,%.1f) can=%s near=%s",name,x,y,tostring(ok),table.concat(names,","))
end
return table.concat(lines,"\n")
