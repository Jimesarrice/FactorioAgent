local s=game.surfaces.nauvis
local e=s.find_entity("stone-furnace",{-64,63})
local t={}
local maxi=e.get_max_inventory_index()
for i=1,maxi do local inv=e.get_inventory(i) if inv then local p={} for _,it in pairs(inv.get_contents()) do p[#p+1]=it.name.."x"..it.count end t[#t+1]="inv"..i.."["..table.concat(p,",").."]" end end
t[#t+1]="st="..tostring(e.status)
return table.concat(t," | ")
