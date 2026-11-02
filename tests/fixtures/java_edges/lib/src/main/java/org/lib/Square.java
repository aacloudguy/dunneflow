package org.lib;

public class Square implements Shape {
    private final double side;

    public Square(double side) {
        this.side = side;
    }

    @Override
    public double area() {
        return side * side;
    }

    public final String label() {
        return "square";
    }

    public static Square unit() {
        return new Square(1);
    }
}
