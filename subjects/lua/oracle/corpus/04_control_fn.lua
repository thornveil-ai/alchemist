-- control flow, closures, varargs, recursion, multiple returns, goto
local function fib(n) if n < 2 then return n end return fib(n-1) + fib(n-2) end
print(fib(10), fib(15))
local function counter()
  local n = 0
  return function() n = n + 1; return n end
end
local c = counter(); print(c(), c(), c())
local function sum(...) local s=0 for _,v in ipairs({...}) do s=s+v end return s, select('#', ...) end
print(sum(1,2,3,4,5))
local function divmod(a,b) return a//b, a%b end
print(divmod(17, 5))
local i = 0
::top:: i = i + 1; if i < 4 then goto top end
print("goto reached", i)
local x = 10
if x > 5 then print("big") elseif x > 0 then print("small") else print("neg") end
local acc = 1
for k = 1, 5 do acc = acc * k end
print("5! =", acc)
local n, s = 0, ""
while n < 3 do n = n + 1; s = s .. n end
repeat s = s .. "x" until #s > 5
print(s)
