package gundramleifert.pairing_list.types;

import gundramleifert.pairing_list.MatchMatrix;
import gundramleifert.pairing_list.configs.ScheduleConfig;

public class BoatMatrix {
    public byte[][] mat;
    public int flights;

    public BoatMatrix(ScheduleConfig properties) {
        mat = new byte[properties.boats.length][properties.teams.length];
    }

    public BoatMatrix(BoatMatrix toCopy) {
        byte[][] srcMat = toCopy.mat;
        int len = srcMat[0].length;
        this.mat = new byte[srcMat.length][len];
        for (int i = 0; i < srcMat.length; i++) {
            System.arraycopy(srcMat[i], 0, this.mat[i], 0, len);
        }
        this.flights = toCopy.flights;
    }

    public int[] getBoatDistribution() {
        int[] res = new int[flights + 1];
        for (byte[] vec : mat) {
            for (byte e : vec) {
                res[e]++;
            }
        }
        return res;
    }

    public void add(Flight flight) {
        flights++;
        for (Race race : flight.races) {
            for (int i = 0; i < race.teams.length; i++) {
                mat[i][race.teams[i]]++;
            }
        }
    }

    public double average() {
        int sum = 0;
        for (byte[] vec : mat) {
            for (byte e : vec) {
                sum += e;
            }
        }
        return ((double) sum) / mat.length / mat[0].length;

    }
}
