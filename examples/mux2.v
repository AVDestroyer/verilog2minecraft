// 2:1 mux — exercises $_MUX_ after techmap.
module mux2 (
    input  wire a,
    input  wire b,
    input  wire s,
    output wire y
);
    assign y = s ? b : a;
endmodule
