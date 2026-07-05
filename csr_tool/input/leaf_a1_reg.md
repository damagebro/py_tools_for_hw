# base_info

| item         | type_input |
| :----------- | :--------- |
| reg_bitwidth | 32         |

# reg_define

| offset | reg_name | field | msb | lsb | SW_access | default_value | reg_type | special | description |
| :----- | :------- | :---- | :-- | :-- | :-------- | :------------ | :------- | :------ | :------ |
| 0x0    | ver      | major | 31  | 16  | RO        | 0x1           | status   | -       |         |
|        |          | minor | 15  | 0   | RO        | 0x0           |          | -       |         |
| 0x4    | scratch  | data  | 31  | 0   | RW        | 0x0           | cfg      | -       |         |
| 0x8    | pulse    | trig  | 0   | 0   | W1T       | 0x0           | cmd      | -       |         |
