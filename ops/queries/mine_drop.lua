local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local e
for _,c in pairs(s.find_entities_filtered{type="mining-drill",force="player"}) do if c.unit_number==217 then e=c end end
local dp=e.drop_position
local out={}
for _,r in pairs(s.find_entities_filtered{position=dp,radius=0.8,type="resource"}) do
  local d=math.sqrt((r.position.x-p.position.x)^2+(r.position.y-p.position.y)^2)
  local ok,res=pcall(function() return p.mine_entity(r,false) end)
  out[#out+1]=string.format("%s ok=%s res=%s valid=%s dist=%.1f",r.name,tostring(ok),tostring(res),tostring(r.valid),d)
end
return table.concat(out,"\n")
