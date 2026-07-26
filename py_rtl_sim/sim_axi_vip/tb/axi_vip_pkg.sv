package axi_vip_pkg;

function automatic bit is_space(input byte char);
    return (char == " ") || (char == "\t") || (char == "\n") || (char == "\r");
endfunction

function automatic int find_char(input string text, input string target);
    byte target_char;

    if (target.len() == 0)
        return -1;

    target_char = target.getc(0);
    for (int idx = 0; idx < text.len(); idx++) begin
        if (text.getc(idx) == target_char)
            return idx;
    end
    return -1;
endfunction

function automatic int find_line_comment(input string text);
    for (int idx = 0; idx < text.len() - 1; idx++) begin
        if ((text.getc(idx) == "/") && (text.getc(idx + 1) == "/"))
            return idx;
    end
    return -1;
endfunction

function automatic string trim(input string raw);
    int first;
    int last;

    if (raw.len() == 0)
        return "";

    first = 0;
    last = raw.len() - 1;

    while ((first <= last) && is_space(raw.getc(first)))
        first++;

    while ((last >= first) && is_space(raw.getc(last)))
        last--;

    if (first > last)
        return "";

    return raw.substr(first, last);
endfunction

function automatic string strip_comment(input string raw);
    int hash_pos;
    int slash_pos;
    int cut_pos;

    hash_pos = find_char(raw, "#");
    slash_pos = find_line_comment(raw);
    cut_pos = -1;

    if (hash_pos >= 0)
        cut_pos = hash_pos;
    if ((slash_pos >= 0) && ((cut_pos < 0) || (slash_pos < cut_pos)))
        cut_pos = slash_pos;

    if (cut_pos < 0)
        return raw;
    if (cut_pos == 0)
        return "";
    return raw.substr(0, cut_pos - 1);
endfunction

function automatic string cfg_key(input string prefix, input string field);
    return {prefix, field};
endfunction

function automatic bit cfg_get_string(
    input  string cfg_file,
    input  string key,
    output string value
);
    int fd;
    int eq_pos;
    string line;
    string lhs;
    string rhs;

    fd = $fopen(cfg_file, "r");
    if (fd == 0)
        return 1'b0;

    while (!$feof(fd)) begin
        void'($fgets(line, fd));
        line = trim(strip_comment(line));
        if (line.len() == 0)
            continue;

        eq_pos = find_char(line, "=");
        if (eq_pos <= 0)
            continue;

        lhs = trim(line.substr(0, eq_pos - 1));
        rhs = trim(line.substr(eq_pos + 1, line.len() - 1));
        if (lhs == key) begin
            value = rhs;
            $fclose(fd);
            return 1'b1;
        end
    end

    $fclose(fd);
    return 1'b0;
endfunction

function automatic string cfg_get_string_default(
    input string cfg_file,
    input string key,
    input string default_value
);
    string value;

    if (cfg_get_string(cfg_file, key, value))
        return value;

    return default_value;
endfunction

function automatic longint unsigned str_to_uint(input string text);
    string value;

    value = trim(text);
    if ((value.len() > 2) &&
        (value.getc(0) == "0") &&
        ((value.getc(1) == "x") || (value.getc(1) == "X")))
        return value.atohex();

    return value.atoi();
endfunction

function automatic longint unsigned cfg_get_uint(
    input string cfg_file,
    input string key,
    input longint unsigned default_value
);
    string value;

    if (cfg_get_string(cfg_file, key, value))
        return str_to_uint(value);

    return default_value;
endfunction

function automatic bit cfg_get_bit(
    input string cfg_file,
    input string key,
    input bit default_value
);
    return cfg_get_uint(cfg_file, key, default_value) != 0;
endfunction

function automatic int cfg_get_int(
    input string cfg_file,
    input string key,
    input int default_value
);
    return int'(cfg_get_uint(cfg_file, key, default_value));
endfunction

function automatic int clog2_bytes(input int byte_num);
    int value;
    int width;

    value = byte_num - 1;
    width = 0;
    while (value > 0) begin
        value = value >> 1;
        width++;
    end
    return width;
endfunction

endpackage
