# base_info

| item         | type_input        |
| :----------- | :---------------- |
| reg_bitwidth | 32                |
| author       | dmg               |
| email        | dmg@sensetime.com |

# reg_define

| offset | reg_name | field   | msb | lsb | SW_access | default_value | reg_type | special                                    | description |
| :----- | :------- | :------ | :-- | :-- | :-------- | :------------ | :------- | :----------------------------------------- | :------ |
| 0x0    | mid_cfg  | val     | 31  | 0   | RW        | 0x55AA        | cfg      | -                                          |         |
| 0x100  | leaf_a1  |         |     |     |           |               | slave    | slv_filename=leaf_a1_reg.md, bytesize=0x40 |         |
| 0x200  | leaf_a2  |         |     |     |           |               | slave    | slv_filename=leaf_a2_reg.md |         |
| 0x300  | mid_stat | err_cnt | 15  | 0   | RO        | 0x0           | status   | -                                          |         |
