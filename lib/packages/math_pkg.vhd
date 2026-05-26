-- math_pkg.vhd — Common integer math utilities for FPGA design
--
-- Provides compile-time functions used when sizing counters, address buses,
-- and memory structures.  All functions operate on natural numbers and are
-- evaluated by the synthesizer at elaboration time — they produce no hardware.
--
-- Usage:
--   library ieee;
--   use ieee.std_logic_1164.all;
--   use work.math_pkg.all;
--
--   -- Address bus width for a memory with DEPTH entries:
--   constant ADDR_W : natural := log2_ceil(DEPTH);
--
--   -- Check that a generic depth is a power of two:
--   -- assert is_pow2(DEPTH) report "DEPTH must be a power of two" severity failure;

package math_pkg is

    -- log2_ceil: Ceiling log base-2.
    --
    -- Returns the number of bits required to represent values 0 .. n-1.
    -- Special case: log2_ceil(0) = 0, log2_ceil(1) = 1.
    --
    -- Examples:
    --   log2_ceil(1)   = 1   (1-entry memory still needs 1 address bit)
    --   log2_ceil(2)   = 1
    --   log2_ceil(4)   = 2
    --   log2_ceil(256) = 8
    --   log2_ceil(257) = 9
    function log2_ceil (n : positive) return natural;

    -- is_pow2: Returns true when n is an exact power of two.
    --
    -- Useful in assertions that guard generic parameters which must be
    -- powers of two (e.g. FIFO depths used with binary-to-Gray conversion).
    --
    -- Examples:
    --   is_pow2(1)   = true
    --   is_pow2(4)   = true
    --   is_pow2(6)   = false
    --   is_pow2(256) = true
    function is_pow2 (n : positive) return boolean;

    -- clamp: Constrain an integer to [lo, hi].
    --
    -- Useful for bounding generic parameters to legal hardware ranges at
    -- elaboration time without resorting to if-generate chains.
    function clamp (val, lo, hi : integer) return integer;

end package math_pkg;


package body math_pkg is

    function log2_ceil (n : positive) return natural is
        variable result : natural := 0;
        variable pow    : positive := 1;
    begin
        if n <= 1 then
            return 1;
        end if;
        while pow < n loop
            pow    := pow * 2;
            result := result + 1;
        end loop;
        return result;
    end function log2_ceil;

    function is_pow2 (n : positive) return boolean is
    begin
        return (n mod 2 = 0 or n = 1) and log2_ceil(n) = log2_ceil(n + 1) - 1;
    end function is_pow2;

    function clamp (val, lo, hi : integer) return integer is
    begin
        if val < lo then return lo;
        elsif val > hi then return hi;
        else return val;
        end if;
    end function clamp;

end package body math_pkg;
