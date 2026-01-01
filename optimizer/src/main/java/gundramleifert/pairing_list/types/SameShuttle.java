package gundramleifert.pairing_list.types;

import gundramleifert.pairing_list.Util;

import java.util.ArrayList;
import java.util.List;

public class SameShuttle {
    public Race race;
    public List<Byte> boats=new ArrayList<>(3);

    public SameShuttle(Race race) {
        this.race = race;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        SameShuttle that = (SameShuttle) o;

        if (!race.equals(that.race)) return false;
        return boats.equals(that.boats);
    }

    @Override
    public int hashCode() {
        int result = race.hashCode();
        result = 31 * result + boats.hashCode();
        return result;
    }
}
