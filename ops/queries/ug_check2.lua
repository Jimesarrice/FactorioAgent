local s=game.surfaces.nauvis
local e=s.find_entity("underground-belt",{-48.5,60.5})
local t={}
local function try(k)
  local ok,v=pcall(function() return e[k] end)
  t[#t+1]=k.."="..(ok and (type(v)=="table" and "table" or tostring(v)) or "ERR")
end
for _,k in ipairs({"belt_neighbours","neighbours","underground_belt","max_underground_distance","belt_speed","direction","type","name"}) do try(k) end
return table.concat(t,"\n")
