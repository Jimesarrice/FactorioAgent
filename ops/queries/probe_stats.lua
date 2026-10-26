local out={}
local f=game.forces.player
for _,n in ipairs({"get_item_production_statistics","get_item_consumption_statistics","get_fluid_production_statistics","get_fluid_consumption_statistics"}) do
  local ok,fn=pcall(function() return f[n] end)
  out[#out+1]=n.." ok="..tostring(ok).." type="..tostring(type(fn))
  if ok and type(fn)=="function" then
    local ok2,st=pcall(function() return f[n](game.surfaces.nauvis) end)
    out[#out+1]=" call="..tostring(ok2).." type="..tostring(type(st))
    if ok2 and type(st)=="userdata" then
      local ok3,v=pcall(function() return st.get_input_count("iron-plate") end)
      local ok4,v2=pcall(function() return st.get_output_count("iron-plate") end)
      out[#out+1]=" input="..tostring(ok3)..":"..tostring(v).." output="..tostring(ok4)..":"..tostring(v2)
    end
  end
end
return table.concat(out,"\n")
