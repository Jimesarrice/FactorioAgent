local s=game.surfaces.nauvis
local items={
 {"assembling-machine-1",-11.5,52.5,0},
 {"assembling-machine-1",-7.5,52.5,0},
 {"wooden-chest",-14.5,52.5,0},
 {"inserter",-13.5,52.5,4},
 {"inserter",-9.5,52.5,4},
 {"small-electric-pole",-13.5,51.5,0},
 {"small-electric-pole",-5.5,51.5,0},
 {"small-electric-pole",-9.5,56.5,0},
}
local out={}
for _,it in ipairs(items) do
 local name,x,y,d=it[1],it[2],it[3],it[4]
 local ok=s.can_place_entity{name=name,position={x=x,y=y},direction=d,force=game.forces.player}
 local es=s.find_entities_filtered{area={{x-0.6,y-0.6},{x+0.6,y+0.6}}}
 local names={}
 for _,e in pairs(es) do names[#names+1]=e.name end
 out[#out+1]=string.format("%s(%.1f,%.1f,d%d) can=%s near=%s",name,x,y,d,tostring(ok),table.concat(names,","))
end
return table.concat(out,"\n")
