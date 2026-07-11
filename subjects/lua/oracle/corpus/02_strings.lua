-- string library: format, patterns, sub/find/gsub/rep/byte/char
print(#"hello", ("hello"):upper(), ("HELLO"):lower(), ("abc"):rep(3))
print(("hello world"):sub(1,5), ("hello"):sub(-3), ("hello"):byte(1,3))
print(string.char(72,105), ("hello"):reverse())
print(string.format("%5d|%-5d|%05.2f|%x|%o|%q", 42, 42, 3.14159, 255, 8, 'a"b\n'))
print(("2024-01-15"):match("(%d+)-(%d+)-(%d+)"))
print(("hello world foo"):gsub("%w+", function(w) return w:upper() end))
print(("a,b,c,d"):gsub(",", ";"))
for word in ("the quick brown"):gmatch("%a+") do io.write(word, "|") end
print()
print(("  trim  "):match("^%s*(.-)%s*$"))
print(string.find("hello world", "o"), ("hello"):find("l+"))
