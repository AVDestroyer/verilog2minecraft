// 4-bit sync-reset up-counter — multi-bit state + next-state comb.
module counter4 (
    input  wire       clk,
    input  wire       rst,
    output reg  [3:0] q
);
    always @(posedge clk) begin
        if (rst)
            q <= 4'b0;
        else
            q <= q + 4'd1;
    end
endmodule
