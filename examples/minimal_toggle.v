// Minimal synchronous test design for the Minecraft HDL backend.
//
// Expected behavior:
// - When rst is high on a rising clk edge, q becomes 0.
// - Otherwise, q toggles on each rising clk edge.
//
// This is intentionally tiny but still exercises:
// - one state element
// - a feedback path
// - one combinational next-state inversion
// - synchronous reset selection logic
module minimal_toggle (
    input wire clk,
    input wire rst,
    output reg q
);

always @(posedge clk) begin
    if (rst) begin
        q <= 1'b0;
    end else begin
        q <= ~q;
    end
end

endmodule
