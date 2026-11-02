package org.app;

import java.util.ArrayList;
import java.util.List;
import org.lib.Base;
import org.lib.Repo;
import org.lib.Shape;
import org.lib.Square;
import org.nowhere.Missing;

public class Main extends Base {
    private final Repo repo;

    Main(Repo repo) {
        this.repo = repo;
    }

    @Override
    public void step() {}

    @Override
    public void greet() {
        super.greet();
    }

    int fact(int n) {
        return n <= 1 ? 1 : n * fact(n - 1);
    }

    void fmt(int x) {}

    void fmt(String s) {}

    void run(Shape s, Missing m) {
        double a = s.area();
        Square sq = Square.unit();
        sq.label();
        sq.area();
        new Helper().help();
        fmt(1);
        fmt("one");
        List<String> xs = new ArrayList<>();
        xs.add("x");
        xs.forEach(x -> fact(2));
        Runnable r = new Runnable() {
            @Override
            public void run() {
                fact(3);
            }
        };
        r.run();
        m.go();
        repo.find(1);
        tick();
    }

    public static void main(String[] args) {
        new Main(null).run(null, null);
    }
}
