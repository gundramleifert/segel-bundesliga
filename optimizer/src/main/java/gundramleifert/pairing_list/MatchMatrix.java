package gundramleifert.pairing_list;

import gundramleifert.pairing_list.types.Flight;
import gundramleifert.pairing_list.types.Race;

import java.util.Arrays;

public class MatchMatrix {

    public byte[][] mat;
    int matches = 0;
    int races = 0;
    int flights = 0;

    int boats;

    public byte[] lowerParticipants;


    public MatchMatrix(int teams, int boats) {
        this.mat = new byte[teams][];
        for (int i = 0; i < teams; i++) {
            this.mat[i] = new byte[i];
        }
        lowerParticipants = new byte[teams];
        this.boats = boats;
    }

    public int[] getMatchDistribution() {
        int[] res = new int[flights + 1];
        for (byte[] vec : mat) {
            for (byte v : vec) {
                res[v] += 2;
            }
        }
        return res;
    }

    public double avg() {
        int cnt = 0;
        double sum = 0;
        for (int i = 0; i < this.mat.length; i++) {
            byte[] vec = this.mat[i];
            cnt += vec.length;
            for (int j = 0; j < vec.length; j++) {
                sum += vec[j];
            }
        }
        return sum / cnt;
    }
    public double avgLowerParticipants() {
        double sum = 0;
        for (int i = 0; i < this.lowerParticipants.length; i++) {
            sum+=this.lowerParticipants[i];
        }
        return sum / this.lowerParticipants.length;
    }

    public MatchMatrix(MatchMatrix toCopy) {
        byte[][] srcMat = toCopy.mat;
        this.mat = new byte[srcMat.length][];
        for (int i = 0; i < srcMat.length; i++) {
            byte[] src = srcMat[i];
            byte[] tgt = new byte[src.length];
            this.mat[i] = tgt;
            System.arraycopy(src, 0, tgt, 0, src.length);
        }
        this.lowerParticipants = new byte[toCopy.lowerParticipants.length];
        System.arraycopy(toCopy.lowerParticipants,
                0,
                lowerParticipants,
                0,
                lowerParticipants.length);
        this.matches = toCopy.matches;
        this.races = toCopy.races;
        this.flights = toCopy.flights;
        this.boats = toCopy.boats;
    }

    public void add(Flight flight, boolean sortBoats) {
        if (sortBoats) {
            flight = flight.copy();
            for (Race race : flight.races) {
                Arrays.sort(race.teams);
            }
        }
        add(flight);
    }

    public void add(Flight flight) {
        for (Race r : flight.races) {
            matches += r.teams.length * (r.teams.length - 1);
            for (int idxLower = 0; idxLower < r.teams.length; idxLower++) {
                byte teamLower = r.teams[idxLower];
                for (int idxHigher = idxLower + 1; idxHigher < r.teams.length; idxHigher++) {
                    final byte teamHigher = r.teams[idxHigher];
                    if (teamHigher>=mat.length ||teamLower>=mat.length){
                        continue;
                    }
                    if (teamHigher > teamLower) {
                        mat[teamHigher][teamLower]++;
                    } else {
                        mat[teamLower][teamHigher]++;
                    }

                }
            }
            if (r.hasLowerParticipants(mat.length)) {
                for (byte t : r.teams) {
                    if (t<lowerParticipants.length)
                        this.lowerParticipants[t]++;
                }
            }
        }
        races += flight.races.length;
        flights++;
    }
}
