// Negative example: level-sensitive latches are not compiler targets.
module level_latch (
    input  wire en,
    input  wire d,
    output reg  q
);
    always @*
        if (en)
            q = d;
endmodule
