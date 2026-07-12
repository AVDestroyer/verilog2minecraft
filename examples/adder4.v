// 4-bit ripple adder — multi-bit ports and wider comb cloud.
module adder4 (
    input  wire [3:0] a,
    input  wire [3:0] b,
    output wire [3:0] sum,
    output wire       cout
);
    assign {cout, sum} = a + b;
endmodule
