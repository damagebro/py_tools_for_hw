# base_info

| item            | type_input        |
| :-------------- | :---------------- |
| system_baseaddr | 0xf000_0000       |
| system_bytesize | 0x1_0000          |
| system_prefix   | npu               |
| reg_bitwidth    | 32                |
| author          | dmg               |
| email           | dmg@sensetime.com |

# reg_define

| offset | reg_name | field | msb | lsb | SW_access | default_value | reg_type | special                                   | description |
| :----- | :------- | :---- | :-- | :-- | :-------- | :------------ | :------- | :---------------------------------------- | :---------- |
| 0x0    | top_ctrl | start | 0   | 0   | W1T       | 0x0           | cmd      | -                                         |             |
| 0x4    | top_ver  | date  | 31  | 0   | RO        | 0x20260329    | status   | -                                         |             |
| 0x1000 | mid_a    |       |     |     |           |               | slave    | slv_filename=mid_a_reg.md, bytesize=0x800 |             |
| 0x2000 | mid_b    |       |     |     |           |               | slave    | slv_filename=mid_b_reg.md, bytesize=0x400 |             |
| 0x3000 | test     | data  | 31  | 0   | RW        | 0x0           | cfg      | repeat 4                                  |             |
|        | test     | val   | 31  | 0   | RW        | 0x0           | cfg      | -                                         |             |
| 0x3020 | test     | val   | 31  | 0   | RW        | 0x0           | cfg      | -                                         |             |
|        | test     | val   | 31  | 0   | RW        | 0x0           | cfg      | -                                         |             |
