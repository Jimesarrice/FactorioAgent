local s=game.surfaces.nauvis
local items={
 {"electric-mining-drill",-46,59,4},{"stone-furnace",-44,59,0},
 {"small-electric-pole",-40.5,55.5,0},{"small-electric-pole",-46.5,57.5,0},
 {"electric-mining-drill",22.5,66.5,0},{"stone-furnace",22,64,0},
 {"small-electric-pole",24.5,66.5,0},
}
local out={}
for _,it in ipairs(items) do
 local name,x,y,d=it[1],it[2],it[3],it[4]
 local ok=s.can_place_entity{name=name,position={x=x,y=y},direction=d,force=game.forces.player}
 local es=s.find_entities_filtered{area={{x-0.6,y-0.6},{x+0.6,y+0.6}}}
 local names={}
 for _,e in pairs(es) do names[#names+1]=e.name end
 out[#out+1]=string.format("%s(%.1f,%.1f) can=%s near=%s",name,x,y,tostring(ok),table.concat(names,","))
end
return table.concat(out,"\n")
