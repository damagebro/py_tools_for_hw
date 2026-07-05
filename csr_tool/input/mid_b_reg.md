# base_info

| item         | type_input |
| :----------- | :--------- |
| reg_bitwidth | 32         |

# reg_define

| offset | reg_name | field  | msb | lsb | SW_access | default_value | reg_type | special                                    | description |
| :----- | :------- | :----- | :-- | :-- | :-------- | :------------ | :------- | :----------------------------------------- | :---------- |
| 0x0    | b_cfg    | param  | 31  | 0   | RW        | 0x1234        | cfg      | -                                          |             |
| 0x10   | b_mem    |        |     |     |           |               | mem      | bytesize=0x80                              |             |
| 0x100  | b_slv    |        |     |     |           |               | slave    | slv_filename=leaf_a2_reg.md, bytesize=0xc0 |             |
| 0x200  | b_stat   | status | 0   | 0   | RO        | 0x0           | status   | -                                          |             |
