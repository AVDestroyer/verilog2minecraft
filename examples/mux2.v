// 2:1 mux — ABC decomposes this into the restricted target gate set.
module mux2 (
    input  wire a,
    input  wire b,
    input  wire s,
    output wire y
);
    assign y = s ? b : a;
endmodule
