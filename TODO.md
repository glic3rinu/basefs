.keys/key_name by files instead of single file
how hard would be to write offset [EOF] ? 
prevent direct writes to .keys, use view.grant view.revoke
touch implementation: provide stat update functionallity and forget about create(), 
full state sync


# TODO tests
# TODO stat times and permissions
# TODO refine blockchain choosing strategy
# TODO fs.create should generate a WRITE log line (touch hola)
# TODO verify fucking keys
# TODO lzma.compress before sending
# TODO log hash for convinience
