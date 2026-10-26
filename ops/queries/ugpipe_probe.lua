local s=game.surfaces.nauvis
local e=s.find_entity("pipe-to-ground",{303.5,410.5})
local t={}
for _,k in ipairs({"neighbours","fluid_box","get_fluid_box","get_pipe_connections","pipe_connections","direction","position","name"}) do
  local ok,v=pcall(function() if k=="get_fluid_box" then return e.get_fluid_box(1) elseif k=="get_pipe_connections" then return e.get_pipe_connections() else return e[k] end end)
  t[#t+1]=k.."="..(ok and (type(v)=="table" and "table" or tostring(v)) or "ERR")
end
return table.concat(t," | ")
