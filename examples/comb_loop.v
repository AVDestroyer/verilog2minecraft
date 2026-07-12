// Cross-coupled NOR SR latch — a true combinational cycle (no DFF).
// Negative example: the frontend rejects designs with combinational loops.
module comb_loop (
    input  wire s,
    input  wire r,
    output wire q,
    output wire nq
);
    nor n0 (q,  r, nq);
    nor n1 (nq, s, q);
endmodule
