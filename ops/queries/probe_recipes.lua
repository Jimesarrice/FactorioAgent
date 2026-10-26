local f=game.forces.player
local out={}
local n=0
local samples={}
for name,r in pairs(f.recipes) do
  n=n+1
  if #samples<10 then samples[#samples+1]=name end
end
out[#out+1]="count="..n.." samples="..table.concat(samples,",")
local r=f.recipes["rocket-part"]
out[#out+1]="direct="..tostring(r).." enabled="..tostring(r and r.enabled)
return table.concat(out,"\n")
