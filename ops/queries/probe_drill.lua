local s=game.surfaces.nauvis
local out={}
for _,u in ipairs({217,218,219}) do
  local e
  for _,c in pairs(s.find_entities_filtered{type="mining-drill",force="player"}) do if c.unit_number==u then e=c end end
  if e then
    local function g(k) local ok,v=pcall(function() return e[k] end); return tostring(ok)..":"..tostring(v) end
    out[#out+1]=string.format("#%d status=%s energy=%s mining_progress=%s mining_speed=%s drop=%s",
      u,tostring(e.status),g("energy"),g("mining_progress"),g("mining_speed"),g("drop_position"))
  end
end
return table.concat(out,"\n")
