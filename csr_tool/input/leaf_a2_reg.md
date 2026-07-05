# reg_define

| offset | reg_name | field | msb | lsb | SW_access | default_value | reg_type | special | description |
| :----- | :------- | :---- | :-- | :-- | :-------- | :------------ | :------- | :------ | :------ |
| 0x0    | id       | val   | 31  | 0   | RO        | 0xA2          | status   | -       |         |
| 0x4    | config   | mode  | 7   | 0   | RW        | 0x1           | cfg      | -       |         |
|        |          | en    | 8   | 8   | RW        | 0x0           |          | -       |         |
| 0x8    | int_sts  | err   | 0   | 0   | W1C       | 0x0           | irq      | -       |         |
