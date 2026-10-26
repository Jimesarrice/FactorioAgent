local s=game.surfaces.nauvis
local list={}
for _,e in pairs(s.find_entities_filtered{name="crude-oil",area={{-1700,-1700},{1700,1700}}}) do
  local d=math.sqrt((e.position.x+43)^2+(e.position.y-43)^2)
  list[#list+1]={x=e.position.x,y=e.position.y,a=e.amount,d=d}
end
table.sort(list,function(a,b) return a.d<b.d end)
local out={}
for i=1,math.min(30,#list) do
  local e=list[i]
  out[#out+1]=string.format("%.0f,%.0f amt=%d d=%.0f",e.x,e.y,e.a,e.d)
end
return #list.."\n"..table.concat(out,"\n")
